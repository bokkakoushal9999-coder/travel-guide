import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Backend"))
from app import app

if __name__ == "__main__":
    from waitress import serve
    port = int(os.getenv("PORT", 5000))
    host = "0.0.0.0" if os.getenv("PORT") else "127.0.0.1"
    print(f"Serving Travel Guide production app on http://{host}:{port}")
    serve(app, host=host, port=port)
