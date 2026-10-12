import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from groq import Groq

# Initialize API Keys from environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# Dummy HTTP server to satisfy Render's free Web Service health check
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a concise, direct, and helpful assistant. Provide fast and accurate answers."
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
    # Start dummy web server in a separate thread
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot is ONLINE (24/7 Groq Cloud) ---")
    app.run_polling()
