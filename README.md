# 📦 Amazon Price Tracker Bot

بوت تيليجرام لمتابعة أسعار أمازون تلقائياً مع تنبيهات فورية عند التخفيضات.

---

## ✨ المميزات

- 🔔 تنبيه فوري عند أي تخفيض في السعر
- 🎯 تنبيه عند الوصول للسعر المستهدف
- ⚡ تنبيه عند الاقتراب من الهدف (±10%)
- ⏰ تحديث تلقائي كل 30 دقيقة (قابل للتعديل)
- 🌍 يدعم كل امتدادات أمازون:
  - amazon.eg / amazon.com / amazon.sa / amazon.ae
  - amazon.co.uk / amazon.de / amazon.fr / amazon.it
  - amazon.es / amazon.ca / amazon.co.jp + روابط amzn.to
- 💾 حفظ تاريخ الأسعار في قاعدة بيانات

---

## 🤖 أوامر البوت

| الأمر | الوظيفة |
|-------|---------|
| `/start` | عرض مرحباً والأوامر |
| `/add رابط [سعر_مستهدف]` | إضافة منتج للمتابعة |
| `/list` | عرض كل المنتجات |
| `/check` | فحص الأسعار الآن |
| `/remove رقم` | حذف منتج |
| `/status` | حالة البوت |

**مثال:**
```
/add https://www.amazon.eg/dp/B0ABC12345 500
/add https://amzn.to/XXXXXX
```

---

## 🚀 طريقة النشر على Railway

### 1. رفع على GitHub
```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/USERNAME/amazon-tracker.git
git push -u origin main
```

### 2. Deploy على Railway
1. اذهب إلى [railway.app](https://railway.app)
2. New Project → Deploy from GitHub repo
3. اختار الـ repository
4. اضغط على المشروع → Variables → Add Variables:
   ```
   BOT_TOKEN = your_bot_token
   CHAT_ID   = your_chat_id
   CHECK_INTERVAL_MINUTES = 30
   ```
5. Railway سيشغل البوت تلقائياً!

### 3. تشغيل محلي (للتجربة)
```bash
pip install -r requirements.txt
python bot.py
```

---

## 📁 هيكل المشروع

```
amazon-tracker/
├── bot.py           ← البوت الرئيسي + الأوامر + الجدولة
├── scraper.py       ← سكرابر أسعار أمازون
├── database.py      ← قاعدة البيانات SQLite
├── requirements.txt
├── Procfile
├── railway.json
├── .env.example
└── .gitignore
```

---

## ⚙️ المتغيرات البيئية

| المتغير | الوصف | الافتراضي |
|---------|-------|-----------|
| `BOT_TOKEN` | توكن البوت من @BotFather | مطلوب |
| `CHAT_ID` | معرف محادثتك | مطلوب |
| `CHECK_INTERVAL_MINUTES` | دقائق بين كل فحص | 30 |
