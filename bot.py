import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from groq import Groq

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    # TEST MODE: Try default supported models one by one
    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ]

    success = False
    for model_name in models_to_try:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": user_text}],
                max_tokens=100,
            )
            reply = completion.choices[0].message.content
            print(f"[Success with model]: {model_name}")
            success = True
            break
        except Exception as e:
            print(f"[Failed model {model_name}]: {e}")
            continue

    if not success:
        # If all fail, fetch the exact list allowed by your API key
        try:
            available = client.models.list()
            model_ids = [m.id for m in available.data]
            reply = f"Key active! Accessible models for your key:\n" + "\n".join(model_ids)
        except Exception as e:
            reply = f"API Key Error: {str(e)}"

    await update.message.reply_text(reply)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot Online ---")
    app.run_polling()
