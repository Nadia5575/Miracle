"""
Amazon Price Tracker Bot - Replit Edition v2
@طلعت
"""
import os
import asyncio
import logging
import sqlite3
import re
import random
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
    ConversationHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ─── Config ───────────────────────────────────────────────
BOT_TOKEN  = os.environ.get("BOT_TOKEN",  "8767106185:AAGj59r0n7crVv6u-pINbAI49UbKv9u9thg")
CHAT_ID    = os.environ.get("CHAT_ID",    "874575996")
CHECK_MINS = int(os.environ.get("CHECK_INTERVAL_MINUTES", "30"))
DB_PATH    = "data/tracker.db"

# Conversation states
ASK_URL    = 1
ASK_TARGET = 2

# ─── Logging ──────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ─── Database ─────────────────────────────────────────────
os.makedirs("data", exist_ok=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                url            TEXT NOT NULL,
                asin           TEXT,
                title          TEXT DEFAULT 'Unknown',
                current_price  REAL,
                prev_price     REAL,
                target_price   REAL,
                currency       TEXT DEFAULT 'EGP',
                added_at       TEXT DEFAULT (datetime('now')),
                last_checked   TEXT
            );
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                price       REAL,
                recorded_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
        """)
    logger.info("✅ Database ready")

# ─── Scraper ──────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

def extract_asin(url: str) -> str:
    m = re.search(r"/dp/([A-Z0-9]{10})", url)
    return m.group(1) if m else ""

def clean_url(url: str) -> str:
    asin = extract_asin(url)
    if asin:
        if "amazon.eg" in url:
            return f"https://www.amazon.eg/dp/{asin}"
        else:
            return f"https://www.amazon.com/dp/{asin}"
    return url

def scrape_amazon(url: str) -> dict:
    import urllib.request
    import urllib.error
    import gzip

    url = clean_url(url)
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar-EG,ar;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            try:
                html = gzip.decompress(raw).decode("utf-8", errors="ignore")
            except Exception:
                html = raw.decode("utf-8", errors="ignore")

        # Title
        title = "Unknown"
        for pattern in [
            r'id="productTitle"[^>]*>\s*(.+?)\s*</span>',
            r'<title>([^|<]{10,})',
        ]:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                title = re.sub(r'\s+', ' ', m.group(1)).strip()
                if len(title) > 10:
                    break

        # Price
        price = None
        for pattern in [
            r'"priceAmount"\s*:\s*([\d.]+)',
            r'class="a-price-whole">\s*([0-9,]+)',
            r'"price"\s*:\s*"EGP\s*([\d,]+)',
            r'"buyingPrice"\s*:\s*([\d.]+)',
            r'id="priceblock_ourprice"[^>]*>[^0-9]*([\d,]+)',
        ]:
            m = re.search(pattern, html)
            if m:
                try:
                    p = float(m.group(1).replace(",", ""))
                    if p > 0:
                        price = p
                        break
                except Exception:
                    continue

        currency = "EGP" if "amazon.eg" in url else "USD"
        logger.info(f"Scraped | Price: {price} | Title: {title[:40]}")
        return {"title": title, "price": price, "currency": currency, "asin": extract_asin(url), "url": url}

    except Exception as e:
        logger.error(f"Scrape error: {e}")
        return {"title": "Unknown", "price": None, "currency": "EGP", "asin": extract_asin(url), "url": url}

# ─── /start & /help ───────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *أهلاً! أنا بوت متابعة أسعار أمازون*\n\n"
        "📌 *الأوامر:*\n"
        "➕ /add — إضافة منتج\n"
        "📋 /list — المنتجات المتابَعة\n"
        "🔍 /check — فحص الأسعار الآن\n"
        "📊 /status — حالة البوت\n"
        "🗑 /remove [id] — حذف منتج",
        parse_mode="Markdown"
    )

# ─── /add ConversationHandler ─────────────────────────────
async def add_step1_ask_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Step 1: طلب الرابط"""
    await update.message.reply_text(
        "📎 *أرسل رابط المنتج من Amazon:*\n\n"
        "_(أرسل /cancel للإلغاء)_",
        parse_mode="Markdown"
    )
    return ASK_URL

async def add_step2_got_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Step 2: استقبال الرابط، جلب السعر، سؤال عن الهدف"""
    url = update.message.text.strip()

    if "amazon" not in url:
        await update.message.reply_text("❗ الرابط لازم من Amazon، حاول مرة تانية:")
        return ASK_URL

    msg = await update.message.reply_text("⏳ جاري جلب بيانات المنتج...")
    data = scrape_amazon(url)
    ctx.user_data["pending_url"]  = url
    ctx.user_data["pending_data"] = data

    price_text = f"*{data['price']:,.0f} {data['currency']}*" if data["price"] else "⚠️ لم يُجلب (سيُحاول لاحقاً)"

    await msg.edit_text(
        f"✅ *تم جلب المنتج:*\n\n"
        f"📦 {data['title'][:70]}\n"
        f"💰 السعر الحالي: {price_text}\n\n"
        f"🎯 *كم السعر المستهدف؟*\n"
        f"_(أرسل رقم مثل* 500 *— أو* 0 *لمتابعة بدون هدف)_",
        parse_mode="Markdown"
    )
    return ASK_TARGET

async def add_step3_got_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Step 3: استقبال الهدف وحفظ المنتج"""
    text = update.message.text.strip()
    try:
        target = float(text.replace(",", "")) if text != "0" else None
    except ValueError:
        await update.message.reply_text("❗ أرسل رقم فقط، مثال: 500 أو 0")
        return ASK_TARGET

    data = ctx.user_data.get("pending_data", {})
    url  = ctx.user_data.get("pending_url", "")

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (url, asin, title, current_price, target_price, currency) VALUES (?,?,?,?,?,?)",
            (url, data.get("asin",""), data.get("title","Unknown"),
             data.get("price"), target, data.get("currency","EGP"))
        )
        pid = cur.lastrowid
        if data.get("price"):
            conn.execute("INSERT INTO price_history (product_id, price) VALUES (?,?)",
                         (pid, data["price"]))

    price_text  = f"{data['price']:,.0f} {data.get('currency','EGP')}" if data.get("price") else "غير متاح"
    target_text = f"*{target:,.0f} {data.get('currency','EGP')}*" if target else "بدون هدف"

    ctx.user_data.clear()
    await update.message.reply_text(
        f"✅ *تمت الإضافة!*\n\n"
        f"🆔 ID: `{pid}`\n"
        f"📦 {data.get('title','Unknown')[:60]}\n"
        f"💰 السعر الحالي: *{price_text}*\n"
        f"🎯 السعر المستهدف: {target_text}\n\n"
        f"سأخطرك عند تغيير السعر 🔔",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

# ─── /list ────────────────────────────────────────────────
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()

    if not rows:
        await update.message.reply_text("📭 لا يوجد منتجات.\n\nاستخدم /add لإضافة منتج.")
        return

    keyboard = []
    for r in rows:
        price  = f"{r['current_price']:,.0f} {r['currency']}" if r["current_price"] else "غير متاح"
        target = f" | 🎯{r['target_price']:,.0f}" if r["target_price"] else ""
        keyboard.append([
            InlineKeyboardButton(f"#{r['id']} {r['title'][:22]}.. {price}{target}", callback_data=f"info_{r['id']}"),
        ])
        keyboard.append([
            InlineKeyboardButton(f"🗑 حذف", callback_data=f"del_{r['id']}"),
            InlineKeyboardButton(f"🔗 فتح", url=r["url"]),
        ])

    await update.message.reply_text(
        f"📋 *المنتجات المتابَعة ({len(rows)}):*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ─── /check ───────────────────────────────────────────────
async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        await update.message.reply_text("📭 لا يوجد منتجات للفحص.")
        return
    msg = await update.message.reply_text(f"🔍 جاري فحص {count} منتج...")
    result = await check_prices(ctx.application.bot, notify=False)
    await msg.edit_text(f"✅ *نتيجة الفحص:*\n\n{result}", parse_mode="Markdown")

# ─── /status ──────────────────────────────────────────────
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        total  = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        w_tgt  = conn.execute("SELECT COUNT(*) FROM products WHERE target_price IS NOT NULL").fetchone()[0]
    await update.message.reply_text(
        f"📊 *حالة البوت:*\n\n"
        f"📦 المنتجات المتابَعة: *{total}*\n"
        f"🎯 منتجات بهدف: *{w_tgt}*\n"
        f"🕐 الفحص كل: *{CHECK_MINS} دقيقة*\n"
        f"🕒 الوقت: *{datetime.now().strftime('%H:%M:%S')}*",
        parse_mode="Markdown"
    )

# ─── /remove ──────────────────────────────────────────────
async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❗ استخدم: /remove [id]")
        return
    try:
        pid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❗ أرسل رقم صحيح")
        return
    with get_conn() as conn:
        row = conn.execute("SELECT title FROM products WHERE id=?", (pid,)).fetchone()
        if not row:
            await update.message.reply_text(f"❗ لا يوجد منتج بـ ID: {pid}")
            return
        conn.execute("DELETE FROM price_history WHERE product_id=?", (pid,))
        conn.execute("DELETE FROM products WHERE id=?", (pid,))
    await update.message.reply_text(f"🗑 تم حذف: *{row['title'][:50]}*", parse_mode="Markdown")

# ─── Callbacks ────────────────────────────────────────────
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("del_"):
        pid = int(query.data.split("_")[1])
        with get_conn() as conn:
            row = conn.execute("SELECT title FROM products WHERE id=?", (pid,)).fetchone()
            conn.execute("DELETE FROM price_history WHERE product_id=?", (pid,))
            conn.execute("DELETE FROM products WHERE id=?", (pid,))
        name = row["title"][:40] if row else f"#{pid}"
        await query.edit_message_text(f"🗑 تم حذف: *{name}*", parse_mode="Markdown")

    elif query.data.startswith("info_"):
        pid = int(query.data.split("_")[1])
        with get_conn() as conn:
            p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            hist = conn.execute(
                "SELECT price, recorded_at FROM price_history WHERE product_id=? ORDER BY recorded_at DESC LIMIT 5",
                (pid,)
            ).fetchall()
        if not p:
            return
        hist_text = "\n".join(f"  • {h['price']:,.0f} — {h['recorded_at']}" for h in hist) or "  لا يوجد سجل"
        price  = f"{p['current_price']:,.0f} {p['currency']}" if p["current_price"] else "غير متاح"
        target = f"{p['target_price']:,.0f} {p['currency']}" if p["target_price"] else "لا يوجد"
        await query.message.reply_text(
            f"📦 *{p['title'][:60]}*\n\n"
            f"💰 السعر الحالي: *{price}*\n"
            f"🎯 المستهدف: *{target}*\n"
            f"🕐 آخر فحص: {p['last_checked'] or 'لم يُفحص'}\n\n"
            f"📈 *آخر 5 أسعار:*\n{hist_text}",
            parse_mode="Markdown"
        )

# ─── Price Check Job ──────────────────────────────────────
async def check_prices(bot=None, notify=True) -> str:
    with get_conn() as conn:
        products = conn.execute("SELECT * FROM products").fetchall()

    if not products:
        return "لا يوجد منتجات."

    lines = []
    for p in products:
        data      = scrape_amazon(p["url"])
        new_price = data["price"]

        if not new_price:
            lines.append(f"⚠️ #{p['id']} {p['title'][:25]}... تعذّر جلب السعر")
            continue

        old_price = p["current_price"]
        target    = p["target_price"]

        with get_conn() as conn:
            conn.execute(
                "UPDATE products SET current_price=?, prev_price=?, last_checked=? WHERE id=?",
                (new_price, old_price, datetime.now().strftime("%H:%M %d/%m"), p["id"])
            )
            conn.execute("INSERT INTO price_history (product_id, price) VALUES (?,?)", (p["id"], new_price))

        arrow = ""
        if old_price:
            d = new_price - old_price
            arrow = f" {'📉' if d < 0 else ('📈' if d > 0 else '✅')}{abs(d):,.0f}"

        lines.append(f"#{p['id']} {p['title'][:25]}... | {new_price:,.0f} {data['currency']}{arrow}")

        if notify and bot and CHAT_ID:
            if old_price and new_price < old_price:
                diff = old_price - new_price
                await bot.send_message(
                    CHAT_ID,
                    f"📉 *انخفض السعر!*\n\n"
                    f"📦 {p['title'][:60]}\n"
                    f"💰 {old_price:,.0f} ← *{new_price:,.0f} {data['currency']}*\n"
                    f"✅ وفرت: *{diff:,.0f} {data['currency']}*\n"
                    f"🔗 [فتح المنتج]({p['url']})",
                    parse_mode="Markdown"
                )
            if target and new_price <= target:
                await bot.send_message(
                    CHAT_ID,
                    f"🎯 *وصل السعر المستهدف!*\n\n"
                    f"📦 {p['title'][:60]}\n"
                    f"💰 السعر: *{new_price:,.0f} {data['currency']}*\n"
                    f"🎯 المستهدف: {target:,.0f} {data['currency']}\n"
                    f"🔗 [اشتري الآن]({p['url']})",
                    parse_mode="Markdown"
                )

    logger.info(f"✅ Checked {len(products)} products")
    return "\n".join(lines)

# ─── Main ─────────────────────────────────────────────────
async def main():
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # Conversation: /add
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_step1_ask_url)],
        states={
            ASK_URL:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step2_got_url)],
            ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_step3_got_target)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
        allow_reentry=True
    )

    app.add_handler(add_conv)
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_start))
    app.add_handler(CommandHandler("list",   cmd_list))
    app.add_handler(CommandHandler("check",  cmd_check))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CallbackQueryHandler(callback_handler))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_prices, "interval", minutes=CHECK_MINS, args=[app.bot, True])
    scheduler.start()

    logger.info(f"🚀 Bot v2 started | Check every {CHECK_MINS} min")
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
