import logging
import os
import asyncio
from flask import Flask, request, Response
from telegram import Update
from telegram.ext import Application

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
WEBHOOK_URL = 'https://web-production-940d4.up.railway.app'

flask_app = Flask(__name__)
application = None
loop = None

async def setup():
    global application
    from bot import create_application
    from scheduler import start_scheduler

    async def post_init(app):
        start_scheduler(app)
        logger.info("Scheduler started")

    application = create_application(post_init_hook=post_init)
    await application.initialize()
    await application.start()

    webhook_path = f'/webhook/{BOT_TOKEN}'
    await application.bot.set_webhook(
        url=f'{WEBHOOK_URL}{webhook_path}',
        drop_pending_updates=True,
    )
    logger.info(f"Webhook set: {WEBHOOK_URL}{webhook_path}")

@flask_app.route('/')
def index():
    return '🤖 Price Tracker Bot is running!', 200

@flask_app.route('/health')
def health():
    return '{"status":"ok"}', 200, {'Content-Type': 'application/json'}

@flask_app.route(f'/webhook/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if application is None:
        return Response('Not ready', status=503)
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    asyncio.run_coroutine_threadsafe(
        application.process_update(update), loop
    )
    return Response('ok', status=200)

if __name__ == '__main__':
    import threading

    loop = asyncio.new_event_loop()

    def start_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    t = threading.Thread(target=start_loop, daemon=True)
    t.start()

    asyncio.run_coroutine_threadsafe(setup(), loop).result(timeout=30)
    logger.info("Bot ready via webhook")

    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port, use_reloader=False)
