import base64
import os
import re
import time
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

# Load environment variables from Backend/.env if running locally
env_path = os.path.join(os.path.dirname(__file__), "Backend", ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)

# Page Configuration
st.set_page_config(
    page_title="Travel Guide - AI Audio Companion",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700;800&display=swap');
    
    .main-header {
        font-family: 'Playfair Display', serif;
        font-weight: 800;
        color: #111827;
        font-size: 2.6rem;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-family: 'Inter', sans-serif;
        color: #6B7280;
        font-size: 1.05rem;
        margin-bottom: 2rem;
    }
    .place-badge {
        background-color: #FFF1E5;
        color: #FF8A1F;
        font-weight: 700;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 9999px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        display: inline-block;
        margin-bottom: 6px;
    }
    .destination-card {
        border-radius: 1.25rem;
        border: 1px solid #F3F4F6;
        padding: 1rem;
        background: #FFFFFF;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease;
        margin-bottom: 1.5rem;
    }
    .transcript-box {
        background-color: #F9FAFB;
        border: 1px solid #E5E7EB;
        border-radius: 1rem;
        padding: 1.5rem;
        font-size: 1rem;
        line-height: 1.8;
        color: #374151;
        margin-top: 1rem;
    }
    .stButton>button {
        background: linear-gradient(135deg, #FF8A1F 0%, #FF6A00 100%);
        color: white;
        font-weight: 700;
        border-radius: 0.75rem;
        border: none;
        padding: 0.75rem 2rem;
        font-size: 1rem;
        box-shadow: 0 10px 25px -5px rgba(255, 138, 31, 0.4);
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px -5px rgba(255, 138, 31, 0.5);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# API Keys Resolution (Supports Streamlit Secrets and Environment Variables)
def get_secret(key_name, default=""):
    try:
        if key_name in st.secrets:
            val = str(st.secrets[key_name]).strip()
            if val and not val.lower().startswith("your_"):
                return val
    except Exception:
        pass
    val = os.getenv(key_name, default).strip()
    if val and not val.lower().startswith("your_"):
        return val
    return default

GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
MURF_API_KEY = get_secret("MURF_API_KEY")
GEMINI_MODEL = get_secret("GEMINI_MODEL", "gemini-3.5-flash")
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

FEATURED_DESTINATIONS = [
    {
        "name": "Taj Mahal",
        "city": "Agra",
        "category": "World Wonder",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Taj_Mahal_%28Edited%29.jpeg",
        "desc": "An immense mausoleum of white marble, built in Agra between 1631 and 1648.",
    },
    {
        "name": "Red Fort",
        "city": "New Delhi",
        "category": "Historical Fort",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Delhi_fort.jpg",
        "desc": "A historic fort in New Delhi that served as the main residence of the Mughal Emperors.",
    },
    {
        "name": "Gateway of India",
        "city": "Mumbai",
        "category": "Monument",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Mumbai_03-2016_30_Gateway_of_India.jpg",
        "desc": "An iconic arch-monument built during the 20th century in Mumbai.",
    },
    {
        "name": "Hawa Mahal",
        "city": "Jaipur",
        "category": "Architecture",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/East_facade_Hawa_Mahal_Jaipur_from_ground_level_%28July_2022%29_-_img_01.jpg",
        "desc": "The 'Palace of Winds' made with intricate red and pink sandstone in Jaipur.",
    },
    {
        "name": "Golden Temple",
        "city": "Amritsar",
        "category": "Spiritual",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/The_Golden_Temple_of_Amrithsar_7.jpg",
        "desc": "Sri Harmandir Sahib, the holiest and most revered Gurdwara of Sikhism.",
    },
    {
        "name": "Mysore Palace",
        "city": "Mysore",
        "category": "Royal Palace",
        "image": "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/Mysore_Palace_Morning.jpg",
        "desc": "A historical palace and royal residence of the Wadiyar dynasty in Karnataka.",
    },
]

PROMPTS = {
    "Summary": """You are a professional tourist guide. Provide a high-level overview of "{place}" in {language}.
Focus on historical significance, why the place is famous, and key architectural highlights.
Keep it concise, engaging, and easy to follow. Limit response to around 200 words. Respond ONLY in {language}.""",
    "Detailed": """You are a professional tourist guide. Provide a rich and immersive explanation of "{place}" in {language}.
Cover historical background, architecture, cultural importance, and interesting visitor insights in a storytelling manner.
Limit response to around 400 words. Respond ONLY in {language}.""",
}


def generate_guide_text(place, length, language):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured. Add it to Streamlit Secrets or Backend/.env.")

    prompt = PROMPTS[length].format(place=place, language=language)
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    models_to_try = [GEMINI_MODEL, "gemini-3.5-flash", "gemini-3.8-flash", "gemini-2.5-flash"]
    last_err = None

    for m in models_to_try:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res.text and res.text.strip():
                return res.text.strip()
        except Exception as e:
            last_err = e
            try:
                res = client.interactions.create(model=m, input=prompt)
                if res.output_text and res.output_text.strip():
                    return res.output_text.strip()
            except Exception:
                pass
            continue
            
    raise RuntimeError(f"Gemini generation failed: {last_err}")


def generate_speech_audio(text, voice_id, locale):
    if not MURF_API_KEY:
        raise ValueError("MURF_API_KEY is not configured. Add it to Streamlit Secrets or Backend/.env.")

    # Voice mapping safeguard
    if voice_id == "Iniya":
        voice_id = "Abirami"

    headers = {
        "api-key": MURF_API_KEY,
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

    resp = requests.post(MURF_STREAM_URL, headers=headers, json=payload, timeout=90)
    if not resp.ok:
        raise RuntimeError(f"Murf TTS request failed ({resp.status_code}): {resp.text[:200]}")
    return resp.content


# --- Sidebar Controls ---
with st.sidebar:
    st.image(
        "https://s3.ap-south-1.amazonaws.com/new-assets.ccbp.in/frontend/loading-data/niat-course-projects/compass-removebg-preview.png",
        width=48,
    )
    st.title("Tour Guide Settings")
    
    selected_language = st.selectbox("Guide Language", list(LANGUAGES.keys()), index=0)
    voice_gender = st.radio("Voice Gender", ["Male", "Female"], horizontal=True)
    voice_id = VOICES[selected_language][voice_gender]
    locale = LANGUAGES[selected_language]
    st.caption(f"Voice Talent: **{voice_id}** ({locale})")
    
    guide_length = st.radio("Detail Level", ["Summary", "Detailed"], horizontal=True, index=0)
    
    st.divider()
    st.markdown("### Service Status")
    gemini_status = "Connected" if GEMINI_API_KEY else "Missing Key"
    murf_status = "Connected" if MURF_API_KEY else "Missing Key"
    st.write(f"- **Gemini AI**: {gemini_status}")
    st.write(f"- **Murf TTS**: {murf_status}")
    if not GEMINI_API_KEY or not MURF_API_KEY:
        st.warning("Please configure your API keys in Streamlit Secrets or Backend/.env")


# --- Main App Interface ---
st.markdown("<div class='main-header'>Travel Guide</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Your Multilingual AI Tourist Companion with Immersive Audio</div>", unsafe_allow_html=True)

# Search & Selection
col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input(
        "Search any global destination or choose a featured place below:",
        placeholder="e.g. Taj Mahal, Colosseum, Eiffel Tower, Kerala Backwaters...",
    )

destination_names = [d["name"] for d in FEATURED_DESTINATIONS]

# Determine active place
if "active_place" not in st.session_state:
    st.session_state.active_place = "Taj Mahal"

if search_query:
    active_place = search_query.strip()
else:
    active_place = st.session_state.active_place

# Featured Destinations Grid
st.markdown("#### Featured Destinations")
cols = st.columns(3)

for idx, dest in enumerate(FEATURED_DESTINATIONS):
    col = cols[idx % 3]
    with col:
        st.image(dest["image"], use_container_width=True)
        st.markdown(f"<span class='place-badge'>{dest['category']} - {dest['city']}</span>", unsafe_allow_html=True)
        st.subheader(dest["name"])
        st.caption(dest["desc"])
        if st.button(f"Select {dest['name']}", key=f"sel_{dest['name']}"):
            st.session_state.active_place = dest["name"]
            st.rerun()

st.divider()

# Experience Panel for Active Place
st.markdown(f"### Exploring: **{active_place}**")
st.write(f"Language: **{selected_language}** | Voice: **{voice_id} ({voice_gender})** | Length: **{guide_length}**")

generate_btn = st.button("Generate Audio Guide", type="primary")

if generate_btn:
    if not active_place:
        st.error("Please enter or select a destination first.")
    elif not GEMINI_API_KEY or not MURF_API_KEY:
        st.error("API keys for Gemini or Murf are missing. Please check your configuration.")
    else:
        with st.status(f"Generating guide for {active_place}...", expanded=True) as status:
            st.write("1. Asking Gemini AI to compose historical guide...")
            try:
                guide_text = generate_guide_text(active_place, guide_length, selected_language)
                st.write("2. Synthesizing voice audio with Murf Falcon-2...")
                audio_bytes = generate_speech_audio(guide_text, voice_id, locale)
                status.update(label="Audio guide generated successfully!", state="complete", expanded=False)
                
                # Store in session state
                st.session_state.last_guide_text = guide_text
                st.session_state.last_audio_bytes = audio_bytes
                st.session_state.last_place = active_place
            except Exception as e:
                status.update(label="Generation failed", state="error", expanded=True)
                st.error(f"Error: {e}")

# Display Results if available
if "last_audio_bytes" in st.session_state and st.session_state.get("last_place") == active_place:
    st.success(f"Audio guide for **{active_place}** is ready!")
    st.audio(st.session_state.last_audio_bytes, format="audio/mp3")
    
    with st.expander("Read Transcript", expanded=True):
        st.markdown(f"<div class='transcript-box'>{st.session_state.last_guide_text}</div>", unsafe_allow_html=True)
