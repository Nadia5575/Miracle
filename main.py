import logging
import os
import threading
import asyncio

from flask import Flask

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ─── Flask (Main Process) ─────────────────────────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route('/')
def index():
    return '🤖 Price Tracker Bot is running!', 200

@flask_app.route('/health')
def health():
    return '{"status":"ok"}', 200, {'Content-Type': 'application/json'}

# ─── Bot (Background Thread) ──────────────────────────────────────────────────
async def post_init(application):
    from scheduler import start_scheduler
    start_scheduler(application)
    logger.info("Scheduler started")

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from bot import create_application
    application = create_application(post_init_hook=post_init)
    logger.info("Bot starting...")
    application.run_polling(drop_pending_updates=True)

# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Bot في background thread
    threading.Thread(target=run_bot, daemon=True).start()
    logger.info("Bot thread started")

    # Flask هو الـ main process — بيخلي Replit صاحي
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Flask starting on port {port}")
    flask_app.run(host='0.0.0.0', port=port, use_reloader=False)
