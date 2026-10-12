import os
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

def get_live_context(user_text: str) -> str:
    """Fetches real-time weather or falls back to DuckDuckGo search."""
    text_lower = user_text.lower()
    
    # 1. Direct weather lookup using wttr.in API
    if "weather" in text_lower or "forecast" in text_lower or "temperature" in text_lower:
        try:
            # Extract basic query or city name
            res = requests.get(f"https://wttr.in/{user_text}?format=3", timeout=5)
            if res.status_code == 200 and res.text.strip():
                return f"Live Weather Data: {res.text.strip()}"
        except Exception as e:
            print(f"Weather API error: {e}")

    # 2. General DuckDuckGo Search fallback
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(user_text, max_results=3):
                results.append(f"Title: {r.get('title')}\nSnippet: {r.get('body')}")
        if results:
            return "\n\n".join(results)
    except Exception as e:
        print(f"Search error: {e}")

    return "No live data retrieved."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    # Fetch live context
    live_info = get_live_context(user_text)

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful and direct AI assistant with access to real-time information. "
                        "When real-time weather or search data is provided below, use it directly to answer "
                        "the user's question accurately.\n\n"
                        f"Real-Time Data:\n{live_info}"
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

    print("--- PangJung_Bot with Live Context is ONLINE ---")
    app.run_polling()
