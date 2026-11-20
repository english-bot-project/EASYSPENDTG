# EasySpend Bot

Telegram bot: kunlik/haftalik/oylik chiqimlarni hisoblaydi (matn, ovoz, chek rasmi).

## Ishga tushirish
1. `pip install -r requirements.txt`
2. `.env.example` ni `.env` ga nusxalab, `BOT_TOKEN` va `GEMINI_API_KEY` ni yozing.
3. `python main.py`

## Hostingda (Railway va h.k.)
`.env` GitHub'ga yuklanmaydi. Kalitlarni hostingning **Variables** bo'limiga kiriting.
Ma'lumotlar saqlanishi uchun Volume ulab, `DB_PATH=/data/bot.db` qo'ying.
