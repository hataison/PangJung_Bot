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

def get_live_weather(query: str) -> str:
    """Extract location and fetch live weather using Open-Meteo geocoding & weather API."""
    try:
        # 1. Search city coordinates using Open-Meteo Geocoding
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        
        if geo_res.get("results"):
            city_info = geo_res["results"][0]
            lat = city_info["latitude"]
            lon = city_info["longitude"]
            city_name = city_info["name"]
            country = city_info.get("country", "")

            # 2. Fetch current weather for coordinates
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            w_res = requests.get(weather_url, timeout=5).json()
            curr = w_res.get("current_weather", {})

            temp = curr.get("temperature")
            wind = curr.get("windspeed")
            
            if temp is not None:
                return f"Current live weather in {city_name}, {country}: Temperature is {temp}°C, Wind Speed is {wind} km/h."
    except Exception as e:
        print(f"Open-Meteo error: {e}")
    return ""

def search_ddg(query: str) -> str:
    """DuckDuckGo fallback search for non-weather queries."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                title = r.get("title", "")
                snippet = r.get("body", "")
                if snippet:
                    results.append(f"- {title}: {snippet}")
        if results:
            return "\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
    return ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    text_lower = user_text.lower()
    live_data = ""

    # Detect weather intent
    if any(k in text_lower for k in ["weather", "temperature", "forecast", "rain"]):
        live_data = get_live_weather(user_text)

    # General web search fallback if no weather data was fetched
    if not live_data:
        live_data = search_ddg(user_text)

    # Prepare prompt
    if live_data:
        system_content = (
            "You are a helpful assistant. Use the following real-time data to answer the user's question directly. "
            "Do NOT state that you lack real-time access.\n\n"
            f"REAL-TIME DATA:\n{live_data}"
        )
    else:
        system_content = "You are a concise, helpful assistant."

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_text}
            ],
            max_tokens=512,
        )
        reply = completion.choices[0].message.content or ""

        # Fail-safe: If the LLM still gives a default disclaimer despite having live data, reply directly with the data
        if live_data and ("don't have access" in reply.lower() or "cannot provide" in reply.lower()):
            reply = f"Here is the real-time weather update:\n\n{live_data}"

    except Exception as e:
        if live_data:
            reply = f"Real-Time Data:\n{live_data}"
        else:
            reply = f"Error: {str(e)}"

    if not reply.strip():
        reply = "Sorry, I couldn't process that request right now."

    print(f"[Sent]: {reply[:50]}...")
    await update.message.reply_text(reply)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot Online ---")
    app.run_polling()
