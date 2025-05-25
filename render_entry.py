import os, threading, asyncio, logging
from main import main as userbot_main  # import your async def main() from main.py

from flask import Flask

# Dummy HTTP server for Render's health check
app_http = Flask(__name__)

@app_http.route("/")
def healthcheck():
    return {"status": "Moon-Userbot alive 🎉"}

def start_http():
    port = int(os.environ.get("PORT", 10000))  # Use Render-assigned port
    app_http.run(host="0.0.0.0", port=port, threaded=True)

# Run both Flask server and Telegram userbot
def main():
    threading.Thread(target=start_http, daemon=True).start()
    asyncio.run(userbot_main())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("Starting Moon-Userbot with Flask healthcheck...")
    main()
