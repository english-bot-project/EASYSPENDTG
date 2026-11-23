# EasySpend Bot + Mini App

Telegram bot: chiqimlarni matn, ovoz va chek rasmi orqali yozadi. Qo'shimcha: kategoriyalar, oylik limit,
kirim, takroriy chiqimlar, Mini App (grafiklar, tarix, tahrirlash), admin statistikasi.

## Fayllar
- `main.py` — bot (asosiy kod)
- `webapp.py` — Mini App uchun xavfsiz API
- `categories.py` — chiqim nomidan kategoriyani aniqlash
- `index.html`, `style.css`, `app.js` — Mini App sahifasi
- `requirements.txt`, `Procfile`, `.python-version` — Railway uchun
- `.env.example` — kalitlar namunasi (haqiqiy `.env` GitHub'ga yuklanmaydi)

## Buyruqlar
`/app` ilova · `/budget 3000000` oylik limit · `/income maosh 5000000` kirim · `/today /week /month /year /undo`
Admin: `/admins` statistika · `/send matn` hammaga xabar

## Kompyuterda sinash
1. `pip install -r requirements.txt`
2. `.env.example` ni `.env` qilib, qiymatlarni yozing
3. `python main.py`
