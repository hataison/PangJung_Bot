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

def fetch_live_info(query: str) -> str:
    """Fetch live data using DuckDuckGo search or weather API."""
    text_lower = query.lower()
    
    # Fast path for weather requests
    if any(k in text_lower for k in ["weather", "temperature", "forecast"]):
        try:
            # Fetch direct one-line weather details via wttr.in
            res = requests.get(f"https://wttr.in/{query}?format=%l:+%C+%t+Humidity:%h+Wind:%w", headers={"User-Agent": "curl/7.68.0"}, timeout=5)
            if res.status_code == 200 and res.text.strip():
                return f"[LIVE WEATHER DATA]: {res.text.strip()}"
        except Exception as e:
            print(f"Weather fetch error: {e}")

    # General web search for other queries
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                title = r.get("title", "")
                snippet = r.get("body", "")
                if snippet:
                    results.append(f"Title: {title}\nSummary: {snippet}")
        if results:
            return "[LIVE WEB SEARCH RESULTS]:\n" + "\n\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        
    return ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    # Fetch live information
    live_data = fetch_live_info(user_text)

    # Build prompt messages: Inject live context directly into user message flow
    messages = []
    
    if live_data:
        full_user_content = (
            f"Here is the verified real-time information retrieved for this query:\n"
            f"{live_data}\n\n"
            f"User Question: {user_text}\n\n"
            f"Answer the user question directly using the real-time information above. Do not claim you lack real-time access."
        )
    else:
        full_user_content = user_text

    messages.append({"role": "user", "content": full_user_content})

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            max_tokens=512,
        )
        reply = completion.choices[0].message.content or "I couldn't generate a response."
    except Exception as e:
        reply = f"Error: {str(e)}"

    if not reply.strip():
        reply = "Sorry, I received an empty response. Please try again."

    print(f"[Sent]: {reply[:50]}...")
    await update.message.reply_text(reply)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot Online ---")
    app.run_polling()
