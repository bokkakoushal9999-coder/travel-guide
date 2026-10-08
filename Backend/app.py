import base64
import logging
import os
import re
import time

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from google import genai
from google.genai.errors import APIError


load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Frontend"))
app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")

cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
if cors_origins_env:
    allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"]

CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins
        }
    },
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
MURF_STREAM_URL = "https://global.api.murf.ai/v1/speech/stream"

LANGUAGES = {
    "English": "en-US",
    "Hindi": "hi-IN",
    "Tamil": "ta-IN",
    "Telugu": "te-IN",
}

VOICES = {
    "English": {"Male": "Matthew", "Female": "Alicia"},
    "Hindi": {"Male": "Aman", "Female": "Namrita"},
    "Tamil": {"Male": "Murali", "Female": "Abirami"},
    "Telugu": {"Male": "Zion", "Female": "Josie"},
}

ANSWER_TYPES = {"Summary", "Detailed"}

DESTINATIONS = [
    {
        "id": "taj-mahal",
        "place": "Taj Mahal",
        "city": "Agra",
        "category": "World Wonder",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Taj_Mahal_%28Edited%29.jpeg",
        "summary": "An immense mausoleum of white marble, built in Agra between 1631 and 1648.",
    },
    {
        "id": "red-fort",
        "place": "Red Fort",
        "city": "New Delhi",
        "category": "Historical Fort",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Delhi_fort.jpg",
        "summary": "A historic fort in the city of Delhi in India that served as the main residence of the Mughal Emperors.",
    },
    {
        "id": "gateway-of-india",
        "place": "Gateway of India",
        "city": "Mumbai",
        "category": "Monument",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Mumbai_03-2016_30_Gateway_of_India.jpg",
        "summary": "An arch-monument built during the 20th century in Bombay, India.",
    },
    {
        "id": "hawa-mahal",
        "place": "Hawa Mahal",
        "city": "Jaipur",
        "category": "Architecture",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/East_facade_Hawa_Mahal_Jaipur_from_ground_level_%28July_2022%29_-_img_01.jpg",
        "summary": "The 'Palace of Winds', a palace in Jaipur, India, made with the red and pink sandstone.",
    },
    {
        "id": "golden-temple",
        "place": "Golden Temple",
        "city": "Amritsar",
        "category": "Spiritual",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/The_Golden_Temple_of_Amrithsar_7.jpg",
        "summary": "Also known as Sri Harmandir Sahib, it is the holiest Gurdwara of Sikhism.",
    },
    {
        "id": "mysore-palace",
        "place": "Mysore Palace",
        "city": "Mysore",
        "category": "Royal Palace",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Mysore_Palace_Morning.jpg",
        "summary": "A historical palace and a royal residence at Mysore in the Indian State of Karnataka.",
    },
]

PROMPTS = {
    "Summary": """
You are a professional tourist guide.
Provide a high-level overview of "{place}" in {language}.

Focus on:
- The historical significance
- Why the place is famous
- Key architectural or cultural highlights

Keep the explanation concise, engaging, and easy to follow.
Avoid excessive details and dates.
Limit the response to around 200 words.
Respond ONLY in {language}.
""",
    "Detailed": """
You are a professional tourist guide.
Provide a detailed and immersive explanation of "{place}" in {language}.

Cover:
- Historical background and timeline
- Architectural design and unique features
- Cultural importance and notable events
- Interesting facts and visitor insights

Explain concepts clearly and in a storytelling manner.
Include relevant details and examples to create a rich experience.
Limit the response to around 400 words.

Respond ONLY in {language}.
""",
}


class ProviderError(Exception):
    def __init__(self, provider, status_code=None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(provider)


def configured_key(name):
    value = os.getenv(name, "").strip()
    if not value or value.lower().startswith("your_"):
        return None
    return value


def generate_description(place, answer_type, language):
    api_key = configured_key("GEMINI_API_KEY")
    if not api_key:
        raise ProviderError("gemini")

    prompt = PROMPTS[answer_type].format(place=place, language=language)
    client = genai.Client(api_key=api_key)

    preferred_model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    models_to_try = [preferred_model]
    for fallback in ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_error = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as error:
            last_error = error
            logger.warning("generate_content failed for %s: %s", model_name, error)
            status = getattr(error, "status_code", getattr(error, "code", None))
            if status in (503, 404, 429):
                continue
            try:
                res = client.interactions.create(
                    model=model_name,
                    input=prompt,
                )
                text = (res.output_text or "").strip()
                if text:
                    return text
            except Exception:
                pass

    status = getattr(last_error, "status_code", getattr(last_error, "code", 502))
    raise ProviderError("gemini", status)



def generate_speech(text, voice_id, locale):
    api_key = configured_key("MURF_API_KEY")
    if not api_key:
        raise ProviderError("murf")

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "voiceId": voice_id,
        "text": text,
        "locale": locale,
        "model": "falcon-2",
        "format": "MP3",
        "sampleRate": 24000,
        "channelType": "MONO",
    }

    try:
        with requests.post(
            MURF_STREAM_URL,
            headers=headers,
            json=payload,
            timeout=(10, 120),
            stream=True,
        ) as response:
            if not response.ok:
                logger.warning("Murf returned non-OK status: %s %s", response.status_code, response.text[:200])
                raise ProviderError("murf", response.status_code)
            audio_bytes = b"".join(response.iter_content(chunk_size=8192))
    except ProviderError:
        raise
    except requests.Timeout:
        raise ProviderError("murf", 504) from None
    except requests.ConnectionError:
        raise ProviderError("murf", 502) from None
    except requests.RequestException:
        raise ProviderError("murf", 502) from None

    if not audio_bytes:
        raise ProviderError("murf", 502)
    return base64.b64encode(audio_bytes).decode("ascii")


def provider_error_response(error):
    if error.provider == "gemini" and not configured_key("GEMINI_API_KEY"):
        return jsonify(error="Set GEMINI_API_KEY in Backend/.env, then restart Flask."), 503
    if error.provider == "murf" and not configured_key("MURF_API_KEY"):
        return jsonify(error="Set MURF_API_KEY in Backend/.env, then restart Flask."), 503

    status_code = error.status_code
    if status_code in (401, 403):
        message = f"The {error.provider.title()} API key is invalid or does not have access."
    elif status_code == 429:
        message = f"The {error.provider.title()} service quota or rate limit was reached."
    elif status_code == 503:
        message = f"The {error.provider.title()} service is currently experiencing high demand. Please try again shortly."
    elif error.provider == "murf" and status_code in (400, 404, 422):
        message = "Murf rejected the selected voice or language. Check that the voice supports this locale."
    elif status_code == 504:
        message = f"The {error.provider.title()} service took too long to respond. Please retry."
    else:
        message = f"The {error.provider.title()} service is temporarily unavailable. Please retry."

    logger.warning("%s provider request failed (status=%s)", error.provider, status_code)
    http_code = 503 if status_code == 503 else (504 if status_code == 504 else 502)
    return jsonify(error=message), http_code


@app.route("/", methods=["GET"])
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify(
        name="Travel Guide API",
        status="running",
        endpoints={
            "health": "/api/health",
            "destinations": "/api/destinations",
            "voices": "/api/voices",
            "generateAudioGuide": "/api/generate-audio-guide",
        },
    ), 200


@app.route("/<path:filename>", methods=["GET"])
def serve_static_file(filename):
    if filename.startswith("api/") or filename == "api":
        return jsonify(error="API endpoint not found."), 404
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify(error="Resource not found."), 404


@app.route("/api/health", methods=["GET"])
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify(
        status="ok",
        service="travel-guide-api",
        version="1.0.0",
        geminiConfigured=bool(configured_key("GEMINI_API_KEY")),
        murfConfigured=bool(configured_key("MURF_API_KEY")),
    ), 200


@app.route("/api/destinations", methods=["GET"])
@app.route("/destinations", methods=["GET"])
def get_destinations():
    query = request.args.get("q", "").strip().lower()
    if query:
        filtered = [
            d
            for d in DESTINATIONS
            if query in d["place"].lower()
            or query in d["city"].lower()
            or query in d["category"].lower()
            or query in d["summary"].lower()
        ]
        return jsonify(destinations=filtered, count=len(filtered)), 200
    return jsonify(destinations=DESTINATIONS, count=len(DESTINATIONS)), 200


@app.route("/api/destinations/<destination_id>", methods=["GET"])
@app.route("/destinations/<destination_id>", methods=["GET"])
def get_destination_by_id(destination_id):
    destination_id = destination_id.strip().lower()
    match = next(
        (
            d
            for d in DESTINATIONS
            if d["id"] == destination_id or d["place"].lower() == destination_id
        ),
        None,
    )
    if not match:
        return jsonify(error="Destination not found."), 404
    return jsonify(destination=match), 200


@app.route("/api/voices", methods=["GET"])
@app.route("/voices", methods=["GET"])
def get_voices():
    return jsonify(
        languages=LANGUAGES,
        voices=VOICES,
    ), 200


@app.route("/api/generate-audio-guide", methods=["POST"])
@app.route("/generate-audio-guide", methods=["POST"])
def generate_audio_guide():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a JSON object with the guide options."), 400

    place = data.get("place")
    answer_type = data.get("answerType")
    language = data.get("language")
    voice_id = data.get("voiceId")
    locale = data.get("locale")

    if not isinstance(place, str) or not place.strip():
        return jsonify(error="Choose or enter a destination."), 400
    place = place.strip()
    if len(place) > 120:
        return jsonify(error="Destination must be 120 characters or fewer."), 400
    if not isinstance(answer_type, str) or answer_type not in ANSWER_TYPES:
        return jsonify(error="Choose Summary or Detailed for the guide length."), 400
    if (
        not isinstance(language, str)
        or language not in LANGUAGES
        or locale != LANGUAGES[language]
    ):
        return jsonify(error="Choose a supported language and matching locale."), 400

    # Auto-map Iniya -> Abirami for Tamil Female compatibility
    if language == "Tamil" and voice_id == "Iniya":
        voice_id = "Abirami"

    if not isinstance(voice_id, str) or not re.fullmatch(r"[A-Za-z0-9 -]{1,80}", voice_id):
        return jsonify(error="Choose a valid voice."), 400

    if not configured_key("GEMINI_API_KEY"):
        return jsonify(error="Set GEMINI_API_KEY in Backend/.env, then restart Flask."), 503
    if not configured_key("MURF_API_KEY"):
        return jsonify(error="Set MURF_API_KEY in Backend/.env, then restart Flask."), 503

    try:
        description = generate_description(place, answer_type, language)
        audio_base64 = generate_speech(description, voice_id, locale)
    except ProviderError as error:
        return provider_error_response(error)

    return jsonify(
        description=description,
        audioBase64=audio_base64,
        audioMimeType="audio/mpeg",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", os.getenv("FLASK_PORT", 5000)))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    host = os.getenv("FLASK_HOST", "0.0.0.0" if os.getenv("PORT") else "127.0.0.1")
    app.run(host=host, port=port, debug=debug)
