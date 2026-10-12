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
    """Fetch live weather or general search results."""
    text_lower = query.lower()
    
    # 1. Weather requests via wttr.in
    if any(k in text_lower for k in ["weather", "temperature", "forecast", "rain", "degrees"]):
        try:
            res = requests.get(
                f"https://wttr.in/{query}?format=%l:+%C,+%t+(Humidity:+%h,+Wind:+%w)",
                headers={"User-Agent": "curl/7.68.0"},
                timeout=5
            )
            if res.status_code == 200 and res.text.strip():
                return res.text.strip()
        except Exception as e:
            print(f"Weather error: {e}")

    # 2. General web search via DuckDuckGo
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                title = r.get("title", "")
                snippet = r.get("body", "")
                if snippet:
                    results.append(f"{title}: {snippet}")
        if results:
            return "\n\n".join(results)
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
        
    return ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    print(f"[Received]: {user_text}")

    await update.message.chat.send_action("typing")

    live_data = fetch_live_info(user_text)

    # Use Qwen model available on your Groq key which follows live context without refusal guardrails
    try:
        if live_data:
            system_prompt = (
                "You are a helpful assistant. The following facts are RETRIEVED IN REAL-TIME. "
                "Answer the user's question accurately using ONLY this retrieved data. "
                "Do not add any disclaimer about real-time access.\n\n"
                f"Retrieved Facts:\n{live_data}"
            )
        else:
            system_prompt = "You are a helpful, direct assistant."

        completion = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=512,
        )
        reply = completion.choices[0].message.content or ""
        
        # Hard safety override: If LLM still gives a canned refusal, output the raw fetched data directly
        if not reply or "don't have access" in reply.lower() or "not able to pull" in reply.lower():
            if live_data:
                reply = f"Here is the latest live data:\n\n{live_data}"
            else:
                reply = "I couldn't retrieve live data for this query. Please try again."

    except Exception as e:
        # Fallback if API fails: send live fetched data directly
        if live_data:
            reply = f"Live Data:\n{live_data}"
        else:
            reply = f"Error: {str(e)}"

    print(f"[Sent]: {reply[:50]}...")
    await update.message.reply_text(reply)

if __name__ == "__main__":
    threading.Thread(target=run_dummy_server, daemon=True).start()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("--- PangJung_Bot Online ---")
    app.run_polling()
