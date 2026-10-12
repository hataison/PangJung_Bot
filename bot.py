import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from groq import Groq
from duckduckgo_search import DDGS

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Bot is live!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

def get_weather_data(user_text: str) -> str:
    """Fetch live weather from Open-Meteo using current_weather=true."""
    text = user_text.lower()
    
    cities = {
        "tokyo": (35.6762, 139.6503, "Tokyo, Japan"),
        "bangkok": (13.7563, 100.5018, "Bangkok, Thailand"),
        "london": (51.5074, -0.1278, "London, UK"),
        "new york": (40.7128, -74.0060, "New York, USA"),
        "singapore": (1.3521, 103.8198, "Singapore"),
    }
    
    selected_city = None
    for name, data in cities.items():
        if name in text:
            selected_city = data
            break
            
    if not selected_city and any(k in text for k in ["weather", "temperature", "forecast"]):
        selected_city = cities["tokyo"]

    if selected_city:
        lat, lon, city_name = selected_city
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json().get("current_weather", {})
                temp = data.get("temperature")
                wind = data.get("windspeed")
                if temp is not None:
                    return f"LIVE WEATHER DATA FOR {city_name}: Temperature is {temp}°C, Wind Speed is {wind} km/h."
        except Exception as e:
            print(f"Weather API Exception: {e}")

    return ""

def search_duckduckgo(query: str) -> str:
    """General web search fallback."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(f"- {r.get('title')}: {r.get('body')}")
        if results:
            return "LIVE WEB SEARCH RESULTS:\n" + "\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo Exception: {e}")
    return ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    # 1. Fetch live weather first
    live_info = get_weather_data(user_text)

    # 2. If weather query was not triggered or returned empty, do web search
    if not live_info:
        live_info = search_duckduckgo(user_text)

    # Build prompt with live context
    if live_info:
        system_content = (
            "You are a helpful AI assistant with real-time web access.\n\n"
            f"{live_info}\n\n"
            "INSTRUCTION: Use the LIVE DATA above to answer the user's question directly and concisely."
        )
    else:
        system_content = "You are a concise, helpful AI assistant."

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_text}
            ],
            max_tokens=512,
        )
        reply = completion.choices[0].message.content
    except Exception as e:
        reply = f"Error: {str(e)}"

    print(f"[Sent]: {reply[:50]}...")
    await update.message.reply_text(reply)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot Online ---")
    app.run_polling()
