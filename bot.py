import os
import re
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from groq import Groq
from duckduckgo_search import DDGS

# Retrieve environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Dummy HTTP server for Render free tier keep-alive
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

def extract_city(text: str) -> str:
    """Extracts the city name from a user prompt if present."""
    match = re.search(r'(?:in|for|at)\s+([a-zA-Z\s]+?)(?:\s+today|\s+now|\?|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Tokyo"  # Fallback target if keyword 'weather' is detected without clear city

def fetch_weather(city: str) -> str:
    """Fetches clean, real-time weather text from wttr.in."""
    try:
        url = f"https://wttr.in/{city}?format=%C+%t+Humidity:{h}+Wind:{w}"
        res = requests.get(url, headers={"User-Agent": "curl/7.68.0"}, timeout=5)
        if res.status_code == 200 and "Unknown" not in res.text:
            return f"Current live weather in {city}: {res.text.strip()}"
    except Exception as e:
        print(f"Weather error: {e}")
    return ""

def search_ddg(query: str) -> str:
    """Fetches live snippets from DuckDuckGo."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(f"Title: {r.get('title')}\nSnippet: {r.get('body')}")
        if results:
            return "\n\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
    return ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    text_lower = user_text.lower()
    live_context = ""

    # Check if user is asking about weather
    if any(k in text_lower for k in ["weather", "temperature", "forecast", "rain", "degrees"]):
        city = extract_city(user_text)
        live_context = fetch_weather(city)

    # Fall back to general web search if no weather context was built
    if not live_context:
        live_context = search_ddg(user_text)

    # Final fallback message
    if not live_context:
        live_context = "No real-time web results found for this query."

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You have real-time access to live data. You MUST use the provided REAL-TIME DATA "
                        "below to answer the user's request directly. Do NOT say 'I don't have access to real-time data'.\n\n"
                        f"REAL-TIME DATA:\n{live_context}"
                    )
                },
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

    print("--- PangJung_Bot with Live Data is ONLINE ---")
    app.run_polling()
