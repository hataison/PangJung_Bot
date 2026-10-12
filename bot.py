import os
import threading
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

def fetch_live_search(query: str) -> str:
    """Performs real-time web search for any prompt using DuckDuckGo."""
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                title = r.get("title", "")
                snippet = r.get("body", "")
                if snippet:
                    results.append(f"Source: {title}\nInfo: {snippet}")
        if results:
            return "\n\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo search error: {e}")
    return "No live search results available."

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    # Always attempt a quick live web search context build
    search_context = fetch_live_search(user_text)

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. Answer the user's message using "
                        "the real-time web search results provided below whenever relevant.\n\n"
                        f"REAL-TIME SEARCH CONTEXT:\n{search_context}"
                    )
                },
                {"role": "user", "content": user_text}
            ],
            max_tokens=512,
        )
        reply = completion.choices[0].message.content or "I couldn't generate a response. Please try asking again."
    except Exception as e:
        reply = f"Error: {str(e)}"

    # Ensure message text is never empty before sending to Telegram
    if not reply.strip():
        reply = "Sorry, I received an empty response. Please try rephrasing your question."

    print(f"[Sent]: {reply[:50]}...")
    await update.message.reply_text(reply)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot with DDG Live Search Online ---")
    app.run_polling()
