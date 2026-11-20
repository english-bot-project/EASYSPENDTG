# ============================================================
#  EASYSPEND BOT
#  Kalitlar bu faylda EMAS — ular .env faylida (yoki hosting Variables bo'limida).
#  Ishga tushirish:  pip install -r requirements.txt  ->  python main.py
# ============================================================

import os


def _load_env(path: str = ".env") -> None:
    """Oddiy .env o'qigich (qo'shimcha kutubxona kerak emas)."""
    full = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    if not os.path.exists(full):
        return
    with open(full, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")

import re
import base64
import difflib
import io
import json
import uuid
import asyncio
import html
import logging
import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


# ───────────────────────── Chiqim matnini tushunish ─────────────────────────
# Bundan kichik summa "tushunarsiz" hisoblanadi va foydalanuvchidan qayta yozish so'raladi
MIN_AMOUNT = 1000

# 1 000 ga ko'paytiruvchi so'zlar (xato yozilganlari ham: ming, min, ing, mng, minga ...)
THOUSAND_WORDS = {"ming", "минг", "мин", "min", "k", "к", "тыс", "тысяч", "ing", "mng", "mig", "mi'ng"}
# 1 000 000 ga ko'paytiruvchi so'zlar (milion, million, milon, miliyon, mln, mil ...)
MILLION_WORDS = {"mln", "mil", "млн", "mlyon", "mlion", "milon", "milion", "million", "miliyon",
                 "милион", "миллион", "мил"}
THOUSAND_FUZZY = ["ming", "минг", "тысяч"]
MILLION_FUZZY = ["million", "milion", "miliyon", "миллион", "милион"]


def _multiplier(word: str):
    w = word.lower()
    if w in THOUSAND_WORDS:
        return 1_000
    if w in MILLION_WORDS:
        return 1_000_000
    if len(w) >= 3:  # taxminiy moslik (mingta, minggg, mlion ...)
        if difflib.get_close_matches(w, MILLION_FUZZY, n=1, cutoff=0.78):
            return 1_000_000
        if difflib.get_close_matches(w, THOUSAND_FUZZY, n=1, cutoff=0.78):
            return 1_000
    return None


NUM_RE = re.compile(
    r"(?<!\d)"
    r"(\d{1,3}(?:[ .,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(?:\s*([^\W\d_]+))?",
    re.IGNORECASE,
)

CURRENCY_RE = re.compile(
    r"(?<![^\W\d_])(so['’ʻ‘`]?m|som|sum|сум|сўм|uzs)(?![^\W\d_])", re.IGNORECASE
)

THOUSANDS_RE = re.compile(r"\d{1,3}(?:[ .,]\d{3})+")


def _to_number(s: str):
    s = s.strip()
    try:
        if THOUSANDS_RE.fullmatch(s):
            return float(re.sub(r"[ .,]", "", s))
        s = s.replace(" ", "")
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        return float(s)
    except ValueError:
        return None


def _candidate(m):
    num = _to_number(m.group(1))
    if num is None:
        return None
    word = m.group(2)
    mult = _multiplier(word) if word else None
    if mult:
        end = m.end()
        if num < 1000:  # "4000 ming" -> 4000, "222 ming" -> 222000
            num *= mult
    else:
        end = m.end(1)
    return num, m.start(), end


def split_items(text: str) -> list[str]:
    parts: list[str] = []
    for line in re.split(r"[\n;]+", text):
        line = line.strip()
        if not line:
            continue
        sub = [p.strip() for p in re.split(r",\s+", line)]
        if len(sub) > 1 and all(re.search(r"\d", p) for p in sub):
            parts.extend(sub)
        else:
            parts.append(line)
    return parts


def _clean_name(s: str) -> str:
    s = CURRENCY_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" -–—:=,.;()[]•*")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:1].upper() + s[1:] if s else ""


def parse_line(line: str):
    best = None
    for m in NUM_RE.finditer(line):
        c = _candidate(m)
        if c and (best is None or c[0] > best[0]):
            best = c
    if best is None or best[0] < MIN_AMOUNT:
        return None
    value, st, en = best
    name = _clean_name(line[:st] + " " + line[en:])
    return name, int(round(value))


def parse_expenses(text: str):
    """(tushunilgan chiqimlar, tushunilmagan qatorlar) qaytaradi."""
    items, bad = [], []
    for part in split_items(text):
        r = parse_line(part)
        if r:
            items.append(r)
        else:
            bad.append(part)
    return items, bad


# ───────────────────────── Matnlar (3 til) ─────────────────────────
LANGS = {"uz": "🇺🇿 O'zbekcha (lotin)", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}

CHOOSE_LANG = (
    "🌍 <b>Tilni tanlang</b>\n"
    "🌍 <b>Выберите язык</b>\n"
    "🌍 <b>Choose your language</b>\n"
    "🌍 <b>Тилни танланг</b>"
)

CUR = {"uz": "so'm", "ru": "сум", "en": "UZS"}

MONTHS = {
    "uz": ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust",
           "Sentabr", "Oktabr", "Noyabr", "Dekabr"],
    "ru": ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
           "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}

T = {
    "uz": {
        "ask_name": "👤 Ism va familiyangizni yozing\n<i>Masalan: Ali Valiyev</i>",
        "ask_age": "🎂 Necha yoshdasiz?\n<i>Faqat raqam yozing, masalan: 25</i>",
        "bad_age": "🙂 Yoshingizni raqam bilan yozing, masalan: <b>25</b>",
        "welcome": (
            "🎉 <b>Xush kelibsiz, {name}!</b>\n\n"
            "Men sizning kunlik chiqimlaringizni hisoblab boraman.\n\n"
            "✍️ <b>Qanday ishlatiladi?</b>\n"
            "Xarid qilganingizda shunchaki yozing:\n"
            "<code>suv-5000</code>\n"
            "<code>go'sht olindi 120000</code>\n"
            "<code>non 4ming</code>\n\n"
            "Bir xabarda bir nechta yozsangiz ham bo'ladi (har birini yangi qatordan).\n\n"
            "🎤 Ovozli xabar yuborsangiz ham bo'ladi,\n"
            "🧾 chek rasmini yuborsangiz ham o'qib beraman.\n\n"
            "🌙 Har kuni 23:59 da kunlik hisobot,\n"
            "📆 Har oyning 1-kuni 00:00 da oylik hisobot,\n"
            "🏆 31-dekabrda yillik reyting yuboraman."
        ),
        "welcome_back": "👋 Qaytganingiz bilan, <b>{name}</b>! Chiqimlaringizni yozishda davom eting.",
        "btn_today": "📅 Bugun",
        "btn_week": "📅 Hafta",
        "btn_month": "📊 Shu oy",
        "btn_year": "🏆 Yil reytingi",
        "btn_undo": "↩️ Oxirgisini o'chirish",
        "btn_lang": "🌍 Til",
        "btn_cancel": "↩️ Bekor qilish",
        "added": "✅ <b>Qo'shildi</b>",
        "today_total": "📅 Bugun jami",
        "month_so_far": "📆 {month} boshidan",
        "no_number": (
            "🙏 Summani aniq tushunolmadim. Iltimos, yana bir bor to'g'ri formatda yozing:\n\n"
            "<code>suv-5000</code>\n"
            "<code>non 4ming</code>\n"
            "<code>go'sht 120000</code>\n"
            "<code>mashina 5 mln</code>"
        ),
        "bad_lines": "🙏 Bu qatorlarni tushunmadim, iltimos, to'g'ri formatda qayta yozing:",
        "not_registered": "Boshlash uchun /start ni bosing 🙂",
        "undone": "↩️ O'chirildi: <b>{name}</b> — {amount}",
        "nothing_to_undo": "Bugun o'chiradigan chiqim yo'q 🙂",
        "cancelled": "↩️ Bekor qilindi",
        "lang_changed": "✅ Til o'zgartirildi",
        "today_title": "📅 <b>Bugungi chiqimlar</b>",
        "daily_title": "🌙 <b>Kun yakuni — {date}</b>",
        "today_empty": "Bugun hali chiqim yozilmagan.",
        "daily_empty": "Bugun chiqim yozilmadi.",
        "month_title": "📊 <b>{month} {year} — oylik hisobot</b>",
        "month_title_partial": "📊 <b>{month} {year} — hozirgacha</b>",
        "total": "💰 Jami chiqim",
        "avg_day": "📈 O'rtacha kunlik",
        "top_day": "🔥 Eng ko'p chiqim kuni",
        "per_day": "🗓 <b>Kunlar bo'yicha</b>",
        "empty_days": "🚫 <b>Chiqimsiz kunlar ({n})</b>",
        "empty_days_none": "🎉 Chiqimsiz kun bo'lmadi — har kuni yozib bordingiz!",
        "month_nodata": "Bu oy uchun ma'lumot yo'q.",
        "year_title": "🏆 <b>{year}-yil — oylar reytingi</b>\n<i>Eng ko'p chiqimdan eng kamigacha</i>",
        "year_avg": "📈 O'rtacha oylik",
        "year_nodata": "Bu yil uchun ma'lumot yo'q.",
        "other": "Boshqa",
        "help": (
            "ℹ️ <b>Yordam</b>\n\n"
            "Chiqimni shunday yozing:\n"
            "<code>suv-5000</code>, <code>non 4ming</code>, <code>4000 ming non</code>\n\n"
            "/week — haftalik chiqim\n"
            "/today — bugungi chiqimlar\n"
            "/month — shu oy hisoboti\n"
            "/year — yillik reyting\n"
            "/undo — oxirgisini o'chirish\n"
            "/lang — tilni o'zgartirish"
        ),
    },
    "ru": {
        "ask_name": "👤 Напишите имя и фамилию\n<i>Например: Али Валиев</i>",
        "ask_age": "🎂 Сколько вам лет?\n<i>Только число, например: 25</i>",
        "bad_age": "🙂 Напишите возраст числом, например: <b>25</b>",
        "welcome": (
            "🎉 <b>Добро пожаловать, {name}!</b>\n\n"
            "Я буду считать ваши ежедневные расходы.\n\n"
            "✍️ <b>Как пользоваться?</b>\n"
            "Просто пишите покупки:\n"
            "<code>вода-5000</code>\n"
            "<code>мясо 120000</code>\n"
            "<code>хлеб 4тыс</code>\n\n"
            "Можно несколько в одном сообщении (каждую с новой строки).\n\n"
            "🎤 Можно отправить голосовое,\n"
            "🧾 или фото чека — я прочитаю.\n\n"
            "🌙 Каждый день в 23:59 — дневной отчёт,\n"
            "📆 1-го числа в 00:00 — отчёт за месяц,\n"
            "🏆 31 декабря — годовой рейтинг."
        ),
        "welcome_back": "👋 С возвращением, <b>{name}</b>! Продолжайте записывать расходы.",
        "btn_today": "📅 Сегодня",
        "btn_week": "📅 Неделя",
        "btn_month": "📊 Этот месяц",
        "btn_year": "🏆 Рейтинг года",
        "btn_undo": "↩️ Удалить последнюю",
        "btn_lang": "🌍 Язык",
        "btn_cancel": "↩️ Отменить",
        "added": "✅ <b>Добавлено</b>",
        "today_total": "📅 Итого за сегодня",
        "month_so_far": "📆 С начала месяца ({month})",
        "no_number": (
            "🙏 Не удалось точно понять сумму. Пожалуйста, напишите ещё раз в правильном формате:\n\n"
            "<code>вода-5000</code>\n"
            "<code>хлеб 4тыс</code>\n"
            "<code>мясо 120000</code>\n"
            "<code>машина 5 млн</code>"
        ),
        "bad_lines": "🙏 Эти строки не удалось понять, напишите их ещё раз в правильном формате:",
        "not_registered": "Нажмите /start, чтобы начать 🙂",
        "undone": "↩️ Удалено: <b>{name}</b> — {amount}",
        "nothing_to_undo": "Сегодня нечего удалять 🙂",
        "cancelled": "↩️ Отменено",
        "lang_changed": "✅ Язык изменён",
        "today_title": "📅 <b>Расходы за сегодня</b>",
        "daily_title": "🌙 <b>Итоги дня — {date}</b>",
        "today_empty": "Сегодня расходов пока нет.",
        "daily_empty": "Сегодня расходы не записаны.",
        "month_title": "📊 <b>{month} {year} — отчёт за месяц</b>",
        "month_title_partial": "📊 <b>{month} {year} — на сегодня</b>",
        "total": "💰 Всего расходов",
        "avg_day": "📈 В среднем за день",
        "top_day": "🔥 Самый затратный день",
        "per_day": "🗓 <b>По дням</b>",
        "empty_days": "🚫 <b>Дни без расходов ({n})</b>",
        "empty_days_none": "🎉 Дней без записей не было — вы записывали каждый день!",
        "month_nodata": "Нет данных за этот месяц.",
        "year_title": "🏆 <b>{year} год — рейтинг месяцев</b>\n<i>От самых затратных к самым скромным</i>",
        "year_avg": "📈 В среднем за месяц",
        "year_nodata": "Нет данных за этот год.",
        "other": "Прочее",
        "help": (
            "ℹ️ <b>Помощь</b>\n\n"
            "Пишите расходы так:\n"
            "<code>вода-5000</code>, <code>хлеб 4тыс</code>, <code>4000 тыс хлеб</code>\n\n"
            "/week — расходы за неделю\n"
            "/today — расходы за сегодня\n"
            "/month — отчёт за месяц\n"
            "/year — годовой рейтинг\n"
            "/undo — удалить последнюю\n"
            "/lang — сменить язык"
        ),
    },
    "en": {
        "ask_name": "👤 Please enter your first and last name\n<i>Example: Ali Valiyev</i>",
        "ask_age": "🎂 How old are you?\n<i>Numbers only, e.g. 25</i>",
        "bad_age": "🙂 Please enter your age as a number, e.g. <b>25</b>",
        "welcome": (
            "🎉 <b>Welcome, {name}!</b>\n\n"
            "I'll keep track of your daily spending.\n\n"
            "✍️ <b>How it works</b>\n"
            "Just type what you bought:\n"
            "<code>water-5000</code>\n"
            "<code>meat 120000</code>\n"
            "<code>bread 4k</code>\n\n"
            "You can add several in one message (one per line).\n\n"
            "🎤 You can send a voice message,\n"
            "🧾 or a photo of a receipt — I'll read it.\n\n"
            "🌙 Every day at 23:59 — daily summary,\n"
            "📆 On the 1st at 00:00 — monthly report,\n"
            "🏆 On Dec 31 — yearly ranking."
        ),
        "welcome_back": "👋 Welcome back, <b>{name}</b>! Keep adding your expenses.",
        "btn_today": "📅 Today",
        "btn_week": "📅 Week",
        "btn_month": "📊 This month",
        "btn_year": "🏆 Year ranking",
        "btn_undo": "↩️ Delete last",
        "btn_lang": "🌍 Language",
        "btn_cancel": "↩️ Undo",
        "added": "✅ <b>Added</b>",
        "today_total": "📅 Today's total",
        "month_so_far": "📆 Since the start of {month}",
        "no_number": (
            "🙏 I couldn't understand the amount. Please write it again in the correct format:\n\n"
            "<code>water-5000</code>\n"
            "<code>bread 4k</code>\n"
            "<code>meat 120000</code>\n"
            "<code>car 5 mln</code>"
        ),
        "bad_lines": "🙏 I couldn't understand these lines, please rewrite them in the correct format:",
        "not_registered": "Press /start to begin 🙂",
        "undone": "↩️ Deleted: <b>{name}</b> — {amount}",
        "nothing_to_undo": "Nothing to delete today 🙂",
        "cancelled": "↩️ Undone",
        "lang_changed": "✅ Language changed",
        "today_title": "📅 <b>Today's expenses</b>",
        "daily_title": "🌙 <b>End of day — {date}</b>",
        "today_empty": "No expenses yet today.",
        "daily_empty": "No expenses were recorded today.",
        "month_title": "📊 <b>{month} {year} — monthly report</b>",
        "month_title_partial": "📊 <b>{month} {year} — so far</b>",
        "total": "💰 Total spent",
        "avg_day": "📈 Daily average",
        "top_day": "🔥 Biggest spending day",
        "per_day": "🗓 <b>By day</b>",
        "empty_days": "🚫 <b>Days with no expenses ({n})</b>",
        "empty_days_none": "🎉 No empty days — you logged every single day!",
        "month_nodata": "No data for this month.",
        "year_title": "🏆 <b>{year} — months ranking</b>\n<i>From highest to lowest spending</i>",
        "year_avg": "📈 Monthly average",
        "year_nodata": "No data for this year.",
        "other": "Other",
        "help": (
            "ℹ️ <b>Help</b>\n\n"
            "Add expenses like this:\n"
            "<code>water-5000</code>, <code>bread 4k</code>, <code>4000 k bread</code>\n\n"
            "/week — weekly spending\n"
            "/today — today's expenses\n"
            "/month — this month's report\n"
            "/year — yearly ranking\n"
            "/undo — delete the last one\n"
            "/lang — change language"
        ),
    },
}

T["uzc"] = {
    "ask_name": "👤 Исм ва фамилиянгизни ёзинг\n<i>Масалан: Али Валиев</i>",
    "ask_age": "🎂 Неча ёшдасиз?\n<i>Фақат рақам ёзинг, масалан: 25</i>",
    "bad_age": "🙂 Ёшингизни рақам билан ёзинг, масалан: <b>25</b>",
    "welcome": (
        "🎉 <b>Хуш келибсиз, {name}!</b>\n\n"
        "Мен сизнинг кунлик чиқимларингизни ҳисоблаб бораман.\n\n"
        "✍️ <b>Қандай ишлатилади?</b>\n"
        "Харид қилганингизда шунчаки ёзинг:\n"
        "<code>сув-5000</code>\n"
        "<code>гўшт олинди 120000</code>\n"
        "<code>нон 4минг</code>\n\n"
        "Бир хабарда бир нечта ёзсангиз ҳам бўлади (ҳар бирини янги қатордан).\n\n"
        "🎤 Овозли хабар юборсангиз ҳам бўлади,\n"
        "🧾 чек расмини юборсангиз ҳам ўқиб бераман.\n\n"
        "🌙 Ҳар куни 23:59 да кунлик ҳисобот,\n"
        "📆 Ҳар ойнинг 1-куни 00:00 да ойлик ҳисобот,\n"
        "🏆 31-декабрда йиллик рейтинг юбораман."
    ),
    "welcome_back": "👋 Қайтганингиз билан, <b>{name}</b>! Чиқимларингизни ёзишда давом этинг.",
    "btn_today": "📅 Бугун",
        "btn_week": "📅 Ҳафта",
    "btn_month": "📊 Шу ой",
    "btn_year": "🏆 Йил рейтинги",
    "btn_undo": "↩️ Охиргисини ўчириш",
    "btn_lang": "🌍 Тил",
    "btn_cancel": "↩️ Бекор қилиш",
    "added": "✅ <b>Қўшилди</b>",
    "today_total": "📅 Бугун жами",
    "month_so_far": "📆 {month} бошидан",
    "no_number": (
        "🙏 Суммани аниқ тушунмадим. Илтимос, яна бир бор тўғри форматда ёзинг:\n\n"
        "<code>сув-5000</code>\n"
        "<code>нон 4минг</code>\n"
        "<code>гўшт 120000</code>\n"
        "<code>машина 5 млн</code>"
    ),
    "bad_lines": "🙏 Бу қаторларни тушунмадим, илтимос, тўғри форматда қайта ёзинг:",
    "not_registered": "Бошлаш учун /start ни босинг 🙂",
    "undone": "↩️ Ўчирилди: <b>{name}</b> — {amount}",
    "nothing_to_undo": "Бугун ўчирадиган чиқим йўқ 🙂",
    "cancelled": "↩️ Бекор қилинди",
    "lang_changed": "✅ Тил ўзгартирилди",
    "today_title": "📅 <b>Бугунги чиқимлар</b>",
    "daily_title": "🌙 <b>Кун якуни — {date}</b>",
    "today_empty": "Бугун ҳали чиқим ёзилмаган.",
    "daily_empty": "Бугун чиқим ёзилмади.",
    "month_title": "📊 <b>{month} {year} — ойлик ҳисобот</b>",
    "month_title_partial": "📊 <b>{month} {year} — ҳозиргача</b>",
    "total": "💰 Жами чиқим",
    "avg_day": "📈 Ўртача кунлик",
    "top_day": "🔥 Энг кўп чиқим куни",
    "per_day": "🗓 <b>Кунлар бўйича</b>",
    "empty_days": "🚫 <b>Чиқимсиз кунлар ({n})</b>",
    "empty_days_none": "🎉 Чиқимсиз кун бўлмади — ҳар куни ёзиб бордингиз!",
    "month_nodata": "Бу ой учун маълумот йўқ.",
    "year_title": "🏆 <b>{year}-йил — ойлар рейтинги</b>\n<i>Энг кўп чиқимдан энг камигача</i>",
    "year_avg": "📈 Ўртача ойлик",
    "year_nodata": "Бу йил учун маълумот йўқ.",
    "other": "Бошқа",
    "help": (
        "ℹ️ <b>Ёрдам</b>\n\n"
        "Чиқимни шундай ёзинг:\n"
        "<code>сув-5000</code>, <code>нон 4минг</code>, <code>4000 минг нон</code>\n\n"
        "🎤 Овозли хабар ёки 🧾 чек расмини юборсангиз ҳам бўлади.\n\n"
        "/week — ҳафталик чиқим\n"
        "/today — бугунги чиқимлар\n"
        "/month — шу ой ҳисоботи\n"
        "/year — йиллик рейтинг\n"
        "/undo — охиргисини ўчириш\n"
        "/lang — тилни ўзгартириш"
    ),
}
MONTHS["uzc"] = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август",
                 "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
CUR["uzc"] = "сўм"
LANGS["uzc"] = "🇺🇿 Ўзбекча (кирилл)"

BTN_KEYS = ("btn_today", "btn_week", "btn_month", "btn_year", "btn_undo", "btn_lang")
BTN_ALL = {k: {T[l][k] for l in T} for k in BTN_KEYS}


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("expense-bot")

TZ = ZoneInfo("Asia/Tashkent")
DB_PATH = os.environ.get("DB_PATH") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")

# ───────────────────────── Ma'lumotlar bazasi ─────────────────────────
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript(
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id    INTEGER PRIMARY KEY,
        lang       TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        age        INTEGER NOT NULL,
        started_on TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS expenses (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day     TEXT NOT NULL,
        name    TEXT NOT NULL,
        amount  INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_exp_user_day ON expenses(user_id, day);
    """
)
db.commit()


def today() -> date:
    return datetime.now(TZ).date()


def get_user(uid: int):
    return db.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()


def fmt(n: float, lang: str) -> str:
    return f"{int(round(n)):,}".replace(",", " ") + " " + CUR[lang]


def esc(s: str) -> str:
    return html.escape(s)


# ───────────────────────── Hisobotlar ─────────────────────────
def sum_between(uid: int, start: date, end: date) -> int:
    row = db.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=? AND day BETWEEN ? AND ?",
        (uid, start.isoformat(), end.isoformat()),
    ).fetchone()
    return row[0]


def today_report(uid: int, lang: str, day: date, auto: bool = False) -> str:
    t = T[lang]
    rows = db.execute(
        "SELECT name, amount FROM expenses WHERE user_id=? AND day=? ORDER BY id",
        (uid, day.isoformat()),
    ).fetchall()
    if auto:
        title = t["daily_title"].format(date=day.strftime("%d.%m.%Y"))
    else:
        title = t["today_title"]
    if not rows:
        empty = t["daily_empty"] if auto else t["today_empty"]
        text = f"{title}\n\n{empty}"
    else:
        lines = [f"🛒 {esc(r['name'] or t['other'])} — {fmt(r['amount'], lang)}" for r in rows]
        text = f"{title}\n\n" + "\n".join(lines)
    total = sum(r["amount"] for r in rows)
    mtd = sum_between(uid, day.replace(day=1), day)
    text += (
        "\n━━━━━━━━━━━━━━\n"
        f"{t['today_total']}: <b>{fmt(total, lang)}</b>\n"
        f"{t['month_so_far'].format(month=MONTHS[lang][day.month - 1])}: <b>{fmt(mtd, lang)}</b>"
    )
    return text



WEEK_T = {
    "uz": {"title": "📅 <b>Haftalik chiqim</b> ({a} – {b})", "total": "💰 Hafta jami", "avg": "📈 O'rtacha kunlik",
           "days": ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"],
           "k": "ming", "m": "mln", "cur": "so'm"},
    "ru": {"title": "📅 <b>Расходы за неделю</b> ({a} – {b})", "total": "💰 Итого за неделю", "avg": "📈 В среднем за день",
           "days": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
           "k": "тыс", "m": "млн", "cur": "сум"},
    "en": {"title": "📅 <b>Weekly spending</b> ({a} – {b})", "total": "💰 Week total", "avg": "📈 Daily average",
           "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
           "k": "k", "m": "mln", "cur": "UZS"},
    "uzc": {"title": "📅 <b>Ҳафталик чиқим</b> ({a} – {b})", "total": "💰 Ҳафта жами", "avg": "📈 Ўртача кунлик",
            "days": ["Душанба", "Сешанба", "Чоршанба", "Пайшанба", "Жума", "Шанба", "Якшанба"],
            "k": "минг", "m": "млн", "cur": "сўм"},
}


def short_amount(n: int, lang: str) -> str:
    """111000 -> '111 ming', 1250000 -> '1.25 mln'"""
    w = WEEK_T[lang]
    if n <= 0:
        return "—"
    if n >= 1_000_000:
        v = round(n / 1_000_000, 2)
        return f"{v:g} {w['m']}"
    if n >= 1000:
        v = round(n / 1000, 1)
        return f"{v:g} {w['k']}"
    return f"{n} {w['cur']}"


def week_report(uid: int, lang: str, day: date) -> str:
    """Joriy hafta: dushanbadan yakshanbagacha, kun bo'yicha chiqim."""
    w = WEEK_T[lang]
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=6)
    rows = db.execute(
        "SELECT day, SUM(amount) s FROM expenses WHERE user_id=? AND day BETWEEN ? AND ? GROUP BY day",
        (uid, monday.isoformat(), sunday.isoformat()),
    ).fetchall()
    per_day = {r["day"]: r["s"] for r in rows}
    top = max(per_day.values(), default=0) or 1
    lines = [w["title"].format(a=monday.strftime("%d.%m"), b=sunday.strftime("%d.%m")), ""]
    total = 0
    for i in range(7):
        d = monday + timedelta(days=i)
        v = per_day.get(d.isoformat(), 0)
        total += v
        mark = "📍" if d == day else "▫️"
        name = f"<b>{w['days'][i]}</b>" if d == day else w["days"][i]
        if d > day and v == 0:
            lines.append(f"{mark} {name} · {d.strftime('%d.%m')}")
            continue
        n = round(6 * v / top)
        bar = "▓" * n + "░" * (6 - n)
        lines.append(f"{mark} {name} · {d.strftime('%d.%m')} — <b>{short_amount(v, lang)}</b>  {bar}")
    passed = (day - monday).days + 1
    lines += ["━━━━━━━━━━━━━━",
              f"{w['total']}: <b>{fmt(total, lang)}</b>",
              f"{w['avg']}: <b>{fmt(total / passed, lang)}</b>"]
    return "\n".join(lines)


def month_report(user, year: int, month: int, upto: date | None = None) -> str:
    """Oylik hisobot. Foydalanuvchi oyning o'rtasida boshlagan bo'lsa, o'sha kundan sanaladi."""
    lang = user["lang"]
    t = T[lang]
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    started = date.fromisoformat(user["started_on"])
    start = max(first, started)
    end = min(last, upto) if upto else last
    if start > end:
        return t["month_nodata"]

    rows = db.execute(
        "SELECT day, SUM(amount) s FROM expenses WHERE user_id=? AND day BETWEEN ? AND ? GROUP BY day",
        (user["user_id"], start.isoformat(), end.isoformat()),
    ).fetchall()
    per_day = {date.fromisoformat(r["day"]): r["s"] for r in rows}
    total = sum(per_day.values())
    days_count = (end - start).days + 1
    empty_days = [
        (start + timedelta(days=i)).day
        for i in range(days_count)
        if (start + timedelta(days=i)) not in per_day
    ]

    partial = upto is not None and upto < last
    title_key = "month_title_partial" if partial else "month_title"
    parts = [t[title_key].format(month=MONTHS[lang][month - 1], year=year), ""]
    parts.append(f"{t['total']}: <b>{fmt(total, lang)}</b>")
    parts.append(f"{t['avg_day']}: <b>{fmt(total / days_count, lang)}</b>")
    if per_day:
        top_d, top_v = max(per_day.items(), key=lambda kv: kv[1])
        parts.append(f"{t['top_day']}: <b>{top_d.strftime('%d.%m')}</b> — {fmt(top_v, lang)}")
        parts += ["", t["per_day"]]
        for d in sorted(per_day):
            parts.append(f"▫️ {d.strftime('%d.%m')} — {fmt(per_day[d], lang)}")
    parts.append("")
    if empty_days:
        parts.append(t["empty_days"].format(n=len(empty_days)))
        parts.append(", ".join(str(d) for d in empty_days))
    else:
        parts.append(t["empty_days_none"])
    return "\n".join(parts)


def year_report(user, year: int, upto: date | None = None) -> str:
    lang = user["lang"]
    t = T[lang]
    started = date.fromisoformat(user["started_on"])
    if started.year > year:
        return t["year_nodata"]
    first_m = started.month if started.year == year else 1
    last_m = upto.month if (upto and upto.year == year) else 12

    rows = db.execute(
        "SELECT substr(day,6,2) m, SUM(amount) s FROM expenses "
        "WHERE user_id=? AND substr(day,1,4)=? GROUP BY m",
        (user["user_id"], str(year)),
    ).fetchall()
    sums = {int(r["m"]): r["s"] for r in rows}
    months = [(m, sums.get(m, 0)) for m in range(first_m, last_m + 1)]
    if not months or not any(v for _, v in months):
        return t["year_nodata"]
    months.sort(key=lambda x: (-x[1], x[0]))
    top = max(v for _, v in months) or 1
    total = sum(v for _, v in months)

    medals = ["🥇", "🥈", "🥉"]
    parts = [t["year_title"].format(year=year), ""]
    for i, (m, v) in enumerate(months):
        mark = medals[i] if i < 3 else f"{i + 1}."
        bar = "▓" * round(8 * v / top) + "░" * (8 - round(8 * v / top))
        parts.append(f"{mark} <b>{MONTHS[lang][m - 1]}</b>\n      {bar}  {fmt(v, lang)}")
    parts += [
        "",
        "━━━━━━━━━━━━━━",
        f"{t['total']}: <b>{fmt(total, lang)}</b>",
        f"{t['year_avg']}: <b>{fmt(total / len(months), lang)}</b>",
    ]
    return "\n".join(parts)


# ───────────────────────── Klaviaturalar ─────────────────────────
def menu(lang: str) -> ReplyKeyboardMarkup:
    t = T[lang]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_week"]), KeyboardButton(text=t["btn_month"])],
            [KeyboardButton(text=t["btn_year"]), KeyboardButton(text=t["btn_undo"])],
            [KeyboardButton(text=t["btn_lang"])],
        ],
        resize_keyboard=True,
    )


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=v, callback_data=f"lang:{k}")] for k, v in LANGS.items()]
    )


# ───────────────────────── Ro'yxatdan o'tish ─────────────────────────
class Reg(StatesGroup):
    name = State()
    age = State()


router = Router()


@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    user = get_user(m.from_user.id)
    if user:  # bir marta ro'yxatdan o'tgan — qayta so'ramaymiz
        await m.answer(
            T[user["lang"]]["welcome_back"].format(name=esc(user["first_name"])),
            reply_markup=menu(user["lang"]),
        )
        return
    await m.answer(CHOOSE_LANG, reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang:"))
async def pick_lang(c: CallbackQuery, state: FSMContext):
    lang = c.data.split(":")[1]
    if lang not in T:
        await c.answer()
        return
    user = get_user(c.from_user.id)
    if user:
        db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, c.from_user.id))
        db.commit()
        await c.message.edit_text(T[lang]["lang_changed"])
        await c.message.answer(T[lang]["help"], reply_markup=menu(lang))
    else:
        await state.update_data(lang=lang)
        await state.set_state(Reg.name)
        await c.message.edit_text(T[lang]["ask_name"])
    await c.answer()


@router.message(Reg.name, F.text)
async def reg_name(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    parts = m.text.strip().split(maxsplit=1)
    if not parts:
        await m.answer(T[lang]["ask_name"])
        return
    await state.update_data(first=parts[0][:50], last=(parts[1] if len(parts) > 1 else "")[:80])
    await state.set_state(Reg.age)
    await m.answer(T[lang]["ask_age"])


@router.message(Reg.age, F.text)
async def reg_age(m: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "uz")
    txt = m.text.strip()
    if not txt.isdigit() or not (3 <= int(txt) <= 120):
        await m.answer(T[lang]["bad_age"])
        return
    db.execute(
        "INSERT OR REPLACE INTO users(user_id, lang, first_name, last_name, age, started_on) VALUES (?,?,?,?,?,?)",
        (m.from_user.id, lang, data["first"], data["last"], int(txt), today().isoformat()),
    )
    db.commit()
    await state.clear()
    await m.answer(T[lang]["welcome"].format(name=esc(data["first"])), reply_markup=menu(lang))


# ───────────────────────── Buyruqlar va tugmalar ─────────────────────────
async def need_user(m: Message):
    user = get_user(m.from_user.id)
    if not user:
        await m.answer(T["uz"]["not_registered"] + "\n" + T["ru"]["not_registered"] + "\n" + T["en"]["not_registered"])
    return user


@router.message(StateFilter(None), Command("help"))
async def cmd_help(m: Message):
    user = await need_user(m)
    if user:
        await m.answer(T[user["lang"]]["help"])


@router.message(StateFilter(None), Command("lang"))
@router.message(StateFilter(None), F.text.in_(BTN_ALL["btn_lang"]))
async def cmd_lang(m: Message):
    await m.answer(CHOOSE_LANG, reply_markup=lang_kb())


@router.message(StateFilter(None), Command("week"))
@router.message(StateFilter(None), F.text.in_(BTN_ALL["btn_week"]))
async def cmd_week(m: Message):
    user = await need_user(m)
    if user:
        await m.answer(week_report(user["user_id"], user["lang"], today()))


@router.message(StateFilter(None), Command("today"))
@router.message(StateFilter(None), F.text.in_(BTN_ALL["btn_today"]))
async def cmd_today(m: Message):
    user = await need_user(m)
    if user:
        await m.answer(today_report(user["user_id"], user["lang"], today()))


@router.message(StateFilter(None), Command("month"))
@router.message(StateFilter(None), F.text.in_(BTN_ALL["btn_month"]))
async def cmd_month(m: Message):
    user = await need_user(m)
    if user:
        d = today()
        await m.answer(month_report(user, d.year, d.month, upto=d))


@router.message(StateFilter(None), Command("year"))
@router.message(StateFilter(None), F.text.in_(BTN_ALL["btn_year"]))
async def cmd_year(m: Message):
    user = await need_user(m)
    if user:
        d = today()
        await m.answer(year_report(user, d.year, upto=d))


@router.message(StateFilter(None), Command("undo"))
@router.message(StateFilter(None), F.text.in_(BTN_ALL["btn_undo"]))
async def cmd_undo(m: Message):
    user = await need_user(m)
    if not user:
        return
    lang = user["lang"]
    row = db.execute(
        "SELECT id, name, amount FROM expenses WHERE user_id=? AND day=? ORDER BY id DESC LIMIT 1",
        (user["user_id"], today().isoformat()),
    ).fetchone()
    if not row:
        await m.answer(T[lang]["nothing_to_undo"])
        return
    db.execute("DELETE FROM expenses WHERE id=?", (row["id"],))
    db.commit()
    await m.answer(
        T[lang]["undone"].format(name=esc(row["name"] or T[lang]["other"]), amount=fmt(row["amount"], lang))
    )
    await m.answer(today_report(user["user_id"], lang, today()))


# ───────────────────────── Chiqim yozish (asosiy qism) ─────────────────────────
@router.message(StateFilter(None), F.text)
async def add_expense(m: Message):
    user = await need_user(m)
    if not user:
        return
    lang = user["lang"]
    t = T[lang]
    items, bad = parse_expenses(m.text)
    if not items:
        await m.answer(t["no_number"])
        return

    d = today()
    ids = []
    for name, amount in items:
        cur = db.execute(
            "INSERT INTO expenses(user_id, day, name, amount) VALUES (?,?,?,?)",
            (user["user_id"], d.isoformat(), name, amount),
        )
        ids.append(str(cur.lastrowid))
    db.commit()

    lines = [f"🛒 {esc(n or t['other'])} — <b>{fmt(a, lang)}</b>" for n, a in items]
    day_total = sum_between(user["user_id"], d, d)
    mtd = sum_between(user["user_id"], d.replace(day=1), d)
    text = (
        f"{t['added']}\n\n" + "\n".join(lines) + "\n━━━━━━━━━━━━━━\n"
        f"{t['today_total']}: <b>{fmt(day_total, lang)}</b>\n"
        f"{t['month_so_far'].format(month=MONTHS[lang][d.month - 1])}: <b>{fmt(mtd, lang)}</b>"
    )
    if bad:
        text += "\n\n" + t["bad_lines"] + "\n" + "\n".join(f"▫️ {esc(b)}" for b in bad)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t["btn_cancel"], callback_data="del:" + ",".join(ids))]]
    )
    await m.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("del:"))
async def cb_delete(c: CallbackQuery):
    user = get_user(c.from_user.id)
    if not user:
        await c.answer()
        return
    ids = [int(x) for x in c.data[4:].split(",") if x.isdigit()]
    if ids:
        db.execute(
            f"DELETE FROM expenses WHERE user_id=? AND id IN ({','.join('?' * len(ids))})",
            (user["user_id"], *ids),
        )
        db.commit()
    await c.message.edit_text(T[user["lang"]]["cancelled"])
    await c.answer()


# ───────────────────────── Ovozli xabar (Gemini) ─────────────────────────
VOICE_PROMPT = """Bu ovozli xabar (o'zbek, rus yoki aralash tilda). Foydalanuvchi o'z xarajatlarini aytyapti.
FAQAT JSON qaytar, boshqa hech narsa yozma:
{"transcript": "aytilgan gapning matni",
 "items": [{"name": "xarid nomi (qisqa, aytilgan tilda)",
            "amount_text": "summa aytilgan so'zlar, masalan '200 ming' yoki '150 dollar'",
            "amount": 200000,
            "currency": "UZS"}]}
Qoidalar:
- ming = 1000, million (milion, mln) = 1000000. amount - to'liq raqam (200 ming -> 200000).
- currency: dollar, $, доллар -> "USD"; evro -> "EUR"; rubl, рубль -> "RUB"; so'm/сум yoki valyuta aytilmasa -> "UZS".
- Summa aytilmagan xarid uchun amount = null.
- Hech narsani o'zing to'qima. Xarajat aytilmagan bo'lsa items bo'sh bo'lsin.
- Har bir alohida xarid - alohida element."""

VT = {
    "uz": {
        "wait": "🎧 Ovozni eshitayapman...",
        "nokey": "🎤 Ovozli xabar hali yoqilmagan (Gemini kaliti kiritilmagan). Hozircha matn bilan yozing 🙂",
        "fail": "😕 Ovozni tushuna olmadim. Qayta yuboring yoki matn bilan yozing.",
        "toolong": "⏱ Ovozli xabar juda uzun. 2 daqiqadan qisqa yuboring.",
        "none": "🤔 Ovozda xarajat topilmadi. Qayta yuboring yoki matn bilan yozing.",
        "heard": "🎤 <b>Men shunday tushundim:</b>",
        "check": "Hammasi to'g'rimi? Tekshirib, <b>Saqlash</b> ni bosing.",
        "nosum": "🙏 Bularning summasi aniq emas (qo'shilmadi), iltimos, matn bilan yozing:",
        "norate": "🙏 Valyuta kursini olib bo'lmadi, bularni so'mda yozing:",
        "warn": "⚠️ tekshiring",
        "save": "✅ Saqlash",
        "cancel": "❌ Bekor qilish",
        "del": "🗑",
        "cancelled": "❌ Bekor qilindi, hech narsa saqlanmadi.",
        "expired": "⌛ Bu xabar eskirgan. Ovozni qayta yuboring.",
        "empty": "Hammasi o'chirildi, hech narsa saqlanmadi.",
    },
    "ru": {
        "wait": "🎧 Слушаю голосовое...",
        "nokey": "🎤 Голосовые ещё не включены (не указан ключ Gemini). Пока пишите текстом 🙂",
        "fail": "😕 Не удалось понять голосовое. Отправьте ещё раз или напишите текстом.",
        "toolong": "⏱ Голосовое слишком длинное. Отправьте короче 2 минут.",
        "none": "🤔 Расходов в голосовом не найдено. Отправьте ещё раз или напишите текстом.",
        "heard": "🎤 <b>Я понял так:</b>",
        "check": "Всё верно? Проверьте и нажмите <b>Сохранить</b>.",
        "nosum": "🙏 Сумма не ясна (не добавлено), напишите текстом:",
        "norate": "🙏 Не удалось получить курс валюты, напишите это в сумах:",
        "warn": "⚠️ проверьте",
        "save": "✅ Сохранить",
        "cancel": "❌ Отмена",
        "del": "🗑",
        "cancelled": "❌ Отменено, ничего не сохранено.",
        "expired": "⌛ Сообщение устарело. Отправьте голосовое заново.",
        "empty": "Всё удалено, ничего не сохранено.",
    },
    "en": {
        "wait": "🎧 Listening...",
        "nokey": "🎤 Voice messages are not enabled yet (no Gemini key). Please type for now 🙂",
        "fail": "😕 I couldn't understand the voice message. Send it again or type it.",
        "toolong": "⏱ Voice message is too long. Please keep it under 2 minutes.",
        "none": "🤔 No expenses found in the voice message. Send it again or type it.",
        "heard": "🎤 <b>Here's what I understood:</b>",
        "check": "Is it correct? Check and press <b>Save</b>.",
        "nosum": "🙏 The amount isn't clear for these (not added), please type them:",
        "norate": "🙏 Couldn't get the exchange rate, please write these in UZS:",
        "warn": "⚠️ check",
        "save": "✅ Save",
        "cancel": "❌ Cancel",
        "del": "🗑",
        "cancelled": "❌ Cancelled, nothing was saved.",
        "expired": "⌛ This message has expired. Please send the voice again.",
        "empty": "Everything removed, nothing was saved.",
    },
}

VT["uzc"] = {
    "wait": "🎧 Овозни эшитяпман...",
    "nokey": "🎤 Овозли хабар ҳали ёқилмаган (Gemini калити киритилмаган). Ҳозирча матн билан ёзинг 🙂",
    "fail": "😕 Овозни тушуна олмадим. Қайта юборинг ёки матн билан ёзинг.",
    "toolong": "⏱ Овозли хабар жуда узун. 2 дақиқадан қисқа юборинг.",
    "none": "🤔 Овозда харажат топилмади. Қайта юборинг ёки матн билан ёзинг.",
    "heard": "🎤 <b>Мен шундай тушундим:</b>",
    "check": "Ҳаммаси тўғрими? Текшириб, <b>Сақлаш</b> ни босинг.",
    "nosum": "🙏 Буларнинг суммаси аниқ эмас (қўшилмади), илтимос, матн билан ёзинг:",
    "norate": "🙏 Валюта курсини олиб бўлмади, буларни сўмда ёзинг:",
    "warn": "⚠️ текширинг",
    "save": "✅ Сақлаш",
    "cancel": "❌ Бекор қилиш",
    "del": "🗑",
    "cancelled": "❌ Бекор қилинди, ҳеч нарса сақланмади.",
    "expired": "⌛ Бу хабар эскирган. Овозни қайта юборинг.",
    "empty": "Ҳаммаси ўчирилди, ҳеч нарса сақланмади.",
}

PENDING: dict = {}          # saqlashni kutayotgan ovozli chiqimlar
_rates_cache = {"day": None, "data": {}}


async def get_rates() -> dict:
    """O'zbekiston Markaziy banki kurslari (1 birlik = necha so'm). Kuniga bir marta olinadi."""
    d = today()
    if _rates_cache["day"] == d and _rates_cache["data"]:
        return _rates_cache["data"]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
        async with s.get("https://cbu.uz/oz/arkhiv-kursov-valyut/json/") as r:
            data = await r.json(content_type=None)
    rates = {}
    for x in data:
        try:
            rates[str(x["Ccy"]).upper()] = float(x["Rate"]) / float(x.get("Nominal") or 1)
        except (KeyError, ValueError, TypeError):
            continue
    _rates_cache["day"], _rates_cache["data"] = d, rates
    return rates


def script_hint(lang: str) -> str:
    if lang == "uzc":
        return "\n- Nomlarni (name) o'zbek KIRILL alifbosida yoz (masalan: гўшт, нон, коммуналка)."
    if lang == "uz":
        return "\n- Nomlarni (name) o'zbek LOTIN alifbosida yoz (masalan: go'sht, non, kommunalka)."
    return ""


def _interaction_text(data: dict) -> str:
    """Interactions API javobidan matnni oladi."""
    texts = []
    for st in data.get("steps") or []:
        if st.get("type") == "model_output":
            for c in st.get("content") or []:
                if isinstance(c, dict) and c.get("type") == "text":
                    texts.append(c.get("text", ""))
    if not texts:  # boshqa shakllar uchun zaxira
        for o in data.get("outputs") or []:
            if isinstance(o, dict) and o.get("type") == "text":
                texts.append(o.get("text", ""))
    if not texts and isinstance(data.get("output_text"), str):
        texts.append(data["output_text"])
    return "".join(texts).strip()


async def _gemini_call(model: str, gen_cfg, audio: bytes, mime: str, timeout: int,
                       prompt: str = VOICE_PROMPT, kind: str = "audio") -> dict:
    url = "https://generativelanguage.googleapis.com/v1beta/interactions"
    body = {
        "model": model,
        "input": [
            {"type": "text", "text": prompt},
            {"type": kind, "data": base64.b64encode(audio).decode(), "mime_type": mime},
        ],
        "store": False,
    }
    if gen_cfg:
        body["generation_config"] = gen_cfg
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as s:
        async with s.post(url, headers={"x-goog-api-key": GEMINI_API_KEY}, json=body) as r:
            raw = await r.text()
            if r.status != 200:
                raise RuntimeError(f"Gemini {model} {r.status}: {raw[:400]}")
    data = json.loads(raw)
    if data.get("status") == "failed":
        raise RuntimeError(f"Gemini {model} failed: {raw[:400]}")
    out = _interaction_text(data)
    if not out:
        raise RuntimeError(f"Gemini {model}: javobda matn topilmadi: {raw[:400]}")
    out = re.sub(r"^```(?:json)?|```$", "", out.strip(), flags=re.M).strip()
    try:
        return json.loads(out)
    except ValueError:
        raise RuntimeError(f"Gemini {model}: JSON emas: {out[:300]}")


async def gemini_extract(audio: bytes, mime: str, prompt: str = VOICE_PROMPT, kind: str = "audio") -> dict:
    """Avval asosiy model (past 'o'ylash' darajasi bilan), bo'lmasa zaxira model."""
    attempts = [(GEMINI_MODEL, {"thinking_level": "low"}, 50)]
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        attempts.append((GEMINI_FALLBACK_MODEL, None, 50))
    last = None
    for model, cfg, timeout in attempts:
        try:
            return await _gemini_call(model, cfg, audio, mime, timeout, prompt, kind)
        except asyncio.TimeoutError:
            last = RuntimeError(f"Gemini {model}: {timeout} soniyada javob bermadi")
            log.warning("%s", last)
        except Exception as e:
            last = e
            log.warning("Gemini xatosi (%s): %s", model, e)
    raise last


def _spoken_amount(text: str):
    best = None
    for m in NUM_RE.finditer(text or ""):
        c = _candidate(m)
        if c and (best is None or c[0] > best):
            best = c[0]
    return best


def build_items(raw_items: list, rates: dict):
    """Gemini javobini tekshirib, so'mga aylantiradi. Summani Gemini emas, bizning qoidalar tasdiqlaydi.
    Qaytaradi: (items, no_sum_names, no_rate_names)"""
    items, no_sum, no_rate = [], [], []
    for it in raw_items or []:
        name = _clean_name(str(it.get("name") or ""))
        cur = str(it.get("currency") or "UZS").upper()
        model_amt = it.get("amount")
        try:
            model_amt = float(model_amt) if model_amt is not None else None
        except (TypeError, ValueError):
            model_amt = None
        mine = _spoken_amount(str(it.get("amount_text") or ""))
        warn = False
        if mine is not None and (model_amt is None or abs(mine - model_amt) > 0.5):
            if model_amt is not None:
                warn = True            # Gemini va bizning hisob farq qildi
            value = mine               # qoidamiz ustun
        else:
            value = model_amt
        if value is None or value <= 0:
            no_sum.append(name or "?")
            continue
        if cur == "UZS" or cur == "SUM":
            uzs = int(round(value))
            if uzs < MIN_AMOUNT:
                warn = True
            shown = ""
        else:
            rate = rates.get(cur)
            if not rate:
                no_rate.append(name or "?")
                continue
            uzs = int(round(value * rate))
            vtxt = f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", " ")
            shown = f"{vtxt} {cur}"
        items.append({"name": name, "uzs": uzs, "orig": shown, "warn": warn})
    return items, no_sum, no_rate


def pending_view(lang: str, pid: str):
    p = PENDING[pid]
    v, t = VT[lang], T[lang]
    lines = []
    for i, it in enumerate(p["items"], 1):
        label = esc(it["name"] or t["other"])
        amt = fmt(it["uzs"], lang)
        if it["orig"]:
            amt = f"{esc(it['orig'])} ≈ {amt}"
        warn = f" {v['warn']}" if it["warn"] else ""
        lines.append(f"{i}. 🛒 {label} — <b>{amt}</b>{warn}")
    text = v["heard"] + "\n\n" + "\n".join(lines)
    if p.get("transcript"):
        text += f"\n\n<i>«{esc(p['transcript'])}»</i>"
    if p.get("no_sum"):
        text += "\n\n" + v["nosum"] + "\n" + "\n".join(f"▫️ {esc(n)}" for n in p["no_sum"])
    if p.get("no_rate"):
        text += "\n\n" + v["norate"] + "\n" + "\n".join(f"▫️ {esc(n)}" for n in p["no_rate"])
    text += "\n\n" + v["check"]
    rows = [[InlineKeyboardButton(text=f"{v['del']} {i}. {(it['name'] or t['other'])[:20]}",
                                  callback_data=f"v:d:{pid}:{i - 1}")]
            for i, it in enumerate(p["items"], 1)]
    rows.append([InlineKeyboardButton(text=v["save"], callback_data=f"v:s:{pid}"),
                 InlineKeyboardButton(text=v["cancel"], callback_data=f"v:c:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(StateFilter(None), F.voice | F.audio)
async def on_voice(m: Message, bot: Bot):
    user = await need_user(m)
    if not user:
        return
    lang = user["lang"]
    v = VT[lang]
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("BU_YERGA"):
        await m.answer(v["nokey"])
        return
    media = m.voice or m.audio
    if (media.duration or 0) > 120:
        await m.answer(v["toolong"])
        return
    mime = "audio/ogg" if m.voice else (m.audio.mime_type or "audio/mpeg")
    wait = await m.answer(v["wait"])
    try:
        buf = io.BytesIO()
        await bot.download(media, destination=buf)
        result = await gemini_extract(buf.getvalue(), mime, prompt=VOICE_PROMPT + script_hint(lang))
        raw_items = result.get("items") or []
        rates = {}
        if any(str(i.get("currency") or "UZS").upper() not in ("UZS", "SUM") for i in raw_items):
            try:
                rates = await get_rates()
            except Exception:
                log.exception("Kursni olib bo'lmadi")
        items, no_sum, no_rate = build_items(raw_items, rates)
    except Exception:
        log.exception("Ovozli xabarni qayta ishlashda xato")
        await wait.edit_text(v["fail"])
        return
    if not items and not no_sum and not no_rate:
        await wait.edit_text(v["none"])
        return
    if not items:
        pid = None
        text = v["nosum"] + "\n" + "\n".join(f"▫️ {esc(n)}" for n in (no_sum + no_rate))
        await wait.edit_text(text)
        return
    now = datetime.now(TZ).timestamp()
    for k in [k for k, x in PENDING.items() if now - x["ts"] > 3600]:
        PENDING.pop(k, None)
    pid = uuid.uuid4().hex[:8]
    PENDING[pid] = {"uid": user["user_id"], "items": items, "ts": now,
                    "transcript": str(result.get("transcript") or "")[:500],
                    "no_sum": no_sum, "no_rate": no_rate}
    text, kb = pending_view(lang, pid)
    await wait.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("v:"))
async def cb_voice(c: CallbackQuery):
    user = get_user(c.from_user.id)
    if not user:
        await c.answer()
        return
    lang = user["lang"]
    v, t = VT[lang], T[lang]
    parts = c.data.split(":")
    action, pid = parts[1], parts[2]
    p = PENDING.get(pid)
    if not p or p.get("kind") == "receipt" or p["uid"] != user["user_id"]:
        await c.message.edit_text(v["expired"])
        await c.answer()
        return
    if action == "c":
        PENDING.pop(pid, None)
        await c.message.edit_text(v["cancelled"])
    elif action == "d":
        idx = int(parts[3])
        if 0 <= idx < len(p["items"]):
            p["items"].pop(idx)
        if not p["items"]:
            PENDING.pop(pid, None)
            await c.message.edit_text(v["empty"])
        else:
            text, kb = pending_view(lang, pid)
            await c.message.edit_text(text, reply_markup=kb)
    elif action == "s":
        PENDING.pop(pid, None)
        d = today()
        ids, lines = [], []
        for it in p["items"]:
            nm = it["name"] + (f" ({it['orig']})" if it["orig"] else "")
            cur = db.execute(
                "INSERT INTO expenses(user_id, day, name, amount) VALUES (?,?,?,?)",
                (user["user_id"], d.isoformat(), nm, it["uzs"]),
            )
            ids.append(str(cur.lastrowid))
            lines.append(f"🛒 {esc(nm or t['other'])} — <b>{fmt(it['uzs'], lang)}</b>")
        db.commit()
        day_total = sum_between(user["user_id"], d, d)
        mtd = sum_between(user["user_id"], d.replace(day=1), d)
        text = (
            f"{t['added']}\n\n" + "\n".join(lines) + "\n━━━━━━━━━━━━━━\n"
            f"{t['today_total']}: <b>{fmt(day_total, lang)}</b>\n"
            f"{t['month_so_far'].format(month=MONTHS[lang][d.month - 1])}: <b>{fmt(mtd, lang)}</b>"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=t["btn_cancel"], callback_data="del:" + ",".join(ids))]]
        )
        await c.message.edit_text(text, reply_markup=kb)
    await c.answer()


# ───────────────────────── Chek rasmi (Gemini) ─────────────────────────
RECEIPT_PROMPT = """Bu do'kon yoki fiskal chekning (kassa cheki) rasmi. Undan ma'lumotni ol.
FAQAT JSON qaytar, boshqa hech narsa yozma:
{"store": "do'kon nomi yoki null",
 "date": "YYYY-MM-DD yoki null",
 "total": 123000,
 "currency": "UZS",
 "items": [{"name": "mahsulot nomi", "amount": 12000}]}
Qoidalar:
- total: chekning OXIRGI to'langan summasi (JAMI / ИТОГО / К ОПЛАТЕ / TO'LOVGA). Chegirma bo'lsa, chegirmadan keyingisi.
- items.amount: shu qatorning umumiy summasi (miqdor x narx), butun raqam, so'mda.
- Raqamlarni bo'sh joysiz, nuqta/vergulsiz yoz (12 000.00 -> 12000).
- QQS, bonus, naqd/qaytim, karta raqami kabi qatorlarni items ga qo'shma.
- Mahsulot nomi chekdagi tilda, qisqa.
- Hech narsani o'zing to'qima. O'qib bo'lmasa null yoz. Chek bo'lmasa items bo'sh bo'lsin."""

RT = {
    "uz": {
        "wait": "🧾 Chekni o'qiyapman...",
        "fail": "😕 Chekni o'qiy olmadim. Rasmni aniqroq (yorug'da, to'liq) qayta yuboring yoki matn bilan yozing.",
        "none": "🤔 Rasmdan chek topilmadi. Chekni to'liq va aniq suratga olib qayta yuboring.",
        "head": "🧾 <b>Chekdan o'qidim:</b>",
        "store": "🏪 Do'kon",
        "date": "📅 Sana",
        "more": "... yana {n} ta mahsulot",
        "total": "💰 Jami",
        "mismatch": "⚠️ Mahsulotlar yig'indisi ({s}) jami summadan farq qiladi (chegirma bo'lishi mumkin). Shuning uchun faqat jami summani saqlash mumkin.",
        "check": "Jami to'g'rimi? Tekshirib, tanlang:",
        "b_total": "💰 Bitta chiqim: {t}",
        "b_items": "🛒 Har bir mahsulot alohida ({n})",
        "b_cancel": "❌ Bekor qilish",
        "cancelled": "❌ Bekor qilindi, hech narsa saqlanmadi.",
        "expired": "⌛ Bu xabar eskirgan. Chekni qayta yuboring.",
        "chek": "Chek",
        "date_note": "(chek sanasi bo'yicha saqlanadi)",
        "toobig": "📷 Rasm juda katta. Kichikroq rasm yuboring.",
    },
    "ru": {
        "wait": "🧾 Читаю чек...",
        "fail": "😕 Не удалось прочитать чек. Отправьте фото чётче (при свете, целиком) или напишите текстом.",
        "none": "🤔 Чек на фото не найден. Сфотографируйте чек целиком и отправьте снова.",
        "head": "🧾 <b>Прочитал с чека:</b>",
        "store": "🏪 Магазин",
        "date": "📅 Дата",
        "more": "... ещё {n} позиций",
        "total": "💰 Итого",
        "mismatch": "⚠️ Сумма позиций ({s}) не совпадает с итогом (возможно, скидка). Поэтому можно сохранить только итоговую сумму.",
        "check": "Итог верный? Проверьте и выберите:",
        "b_total": "💰 Одним расходом: {t}",
        "b_items": "🛒 Каждая позиция отдельно ({n})",
        "b_cancel": "❌ Отмена",
        "cancelled": "❌ Отменено, ничего не сохранено.",
        "expired": "⌛ Сообщение устарело. Отправьте чек заново.",
        "chek": "Чек",
        "date_note": "(сохранится по дате чека)",
        "toobig": "📷 Фото слишком большое. Отправьте поменьше.",
    },
    "en": {
        "wait": "🧾 Reading the receipt...",
        "fail": "😕 I couldn't read the receipt. Send a clearer photo (good light, full receipt) or type it.",
        "none": "🤔 No receipt found in the photo. Take a full, clear picture and send again.",
        "head": "🧾 <b>Read from the receipt:</b>",
        "store": "🏪 Store",
        "date": "📅 Date",
        "more": "... and {n} more items",
        "total": "💰 Total",
        "mismatch": "⚠️ The items sum ({s}) differs from the total (maybe a discount). So only the total can be saved.",
        "check": "Is the total correct? Check and choose:",
        "b_total": "💰 As one expense: {t}",
        "b_items": "🛒 Each item separately ({n})",
        "b_cancel": "❌ Cancel",
        "cancelled": "❌ Cancelled, nothing was saved.",
        "expired": "⌛ This message has expired. Please send the receipt again.",
        "chek": "Receipt",
        "date_note": "(saved under the receipt date)",
        "toobig": "📷 The photo is too large. Send a smaller one.",
    },
}


RT["uzc"] = {
    "wait": "🧾 Чекни ўқияпман...",
    "fail": "😕 Чекни ўқий олмадим. Расмни аниқроқ (ёруғда, тўлиқ) қайта юборинг ёки матн билан ёзинг.",
    "none": "🤔 Расмдан чек топилмади. Чекни тўлиқ ва аниқ суратга олиб қайта юборинг.",
    "head": "🧾 <b>Чекдан ўқидим:</b>",
    "store": "🏪 Дўкон",
    "date": "📅 Сана",
    "more": "... яна {n} та маҳсулот",
    "total": "💰 Жами",
    "mismatch": "⚠️ Маҳсулотлар йиғиндиси ({s}) жами суммадан фарқ қилади (чегирма бўлиши мумкин). Шунинг учун фақат жами суммани сақлаш мумкин.",
    "check": "Жами тўғрими? Текшириб, танланг:",
    "b_total": "💰 Битта чиқим: {t}",
    "b_items": "🛒 Ҳар бир маҳсулот алоҳида ({n})",
    "b_cancel": "❌ Бекор қилиш",
    "cancelled": "❌ Бекор қилинди, ҳеч нарса сақланмади.",
    "expired": "⌛ Бу хабар эскирган. Чекни қайта юборинг.",
    "chek": "Чек",
    "date_note": "(чек санаси бўйича сақланади)",
    "toobig": "📷 Расм жуда катта. Кичикроқ расм юборинг.",
}

def _parse_date(s):
    if not s:
        return None
    s = str(s).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    m = re.match(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if m:
        d_, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        try:
            return date(y, mo, d_)
        except ValueError:
            return None
    return None


def build_receipt(data: dict, started: date, now: date):
    """Gemini javobini tekshiradi. Qaytaradi: dict yoki None (chek topilmasa)."""
    items = []
    for it in data.get("items") or []:
        try:
            amt = float(it.get("amount"))
        except (TypeError, ValueError):
            continue
        if amt <= 0:
            continue
        items.append({"name": _clean_name(str(it.get("name") or "")), "uzs": int(round(amt))})
    try:
        total = float(data.get("total")) if data.get("total") is not None else None
    except (TypeError, ValueError):
        total = None
    items_sum = sum(i["uzs"] for i in items)
    if (total is None or total <= 0) and items_sum > 0:
        total = items_sum
    if total is None or total <= 0:
        return None
    total = int(round(total))
    consistent = abs(items_sum - total) <= max(5, total * 0.005)
    d = _parse_date(data.get("date"))
    day, own_date = now, False
    if d and max(started, now - timedelta(days=45)) <= d <= now:
        day, own_date = d, True
    store = str(data.get("store") or "").strip()[:60]
    return {"store": store, "day": day, "own_date": own_date, "total": total,
            "items": items, "items_sum": items_sum, "consistent": consistent and bool(items)}


def receipt_view(lang: str, pid: str):
    p = PENDING[pid]
    r, t = RT[lang], T[lang]
    lines = [r["head"], ""]
    if p["store"]:
        lines.append(f"{r['store']}: <b>{esc(p['store'])}</b>")
    note = " " + r["date_note"] if p["own_date"] else ""
    lines.append(f"{r['date']}: <b>{p['day'].strftime('%d.%m.%Y')}</b>{note}")
    lines.append("")
    shown = p["items"][:15]
    for it in shown:
        lines.append(f"▫️ {esc(it['name'] or t['other'])} — {fmt(it['uzs'], lang)}")
    if len(p["items"]) > len(shown):
        lines.append(r["more"].format(n=len(p["items"]) - len(shown)))
    lines += ["━━━━━━━━━━━━━━", f"{r['total']}: <b>{fmt(p['total'], lang)}</b>"]
    if p["items"] and not p["consistent"]:
        lines += ["", r["mismatch"].format(s=fmt(p["items_sum"], lang))]
    lines += ["", r["check"]]
    rows = [[InlineKeyboardButton(text=r["b_total"].format(t=fmt(p["total"], lang)), callback_data=f"r:t:{pid}")]]
    if p["consistent"]:
        rows.append([InlineKeyboardButton(text=r["b_items"].format(n=len(p["items"])), callback_data=f"r:i:{pid}")])
    rows.append([InlineKeyboardButton(text=r["b_cancel"], callback_data=f"r:c:{pid}")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(StateFilter(None), F.photo | F.document)
async def on_receipt(m: Message, bot: Bot):
    if m.document and not (m.document.mime_type or "").startswith("image/"):
        return
    user = await need_user(m)
    if not user:
        return
    lang = user["lang"]
    r, v = RT[lang], VT[lang]
    if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("BU_YERGA"):
        await m.answer(v["nokey"])
        return
    if m.photo:
        media, mime = m.photo[-1], "image/jpeg"
    else:
        media, mime = m.document, m.document.mime_type
    if (getattr(media, "file_size", 0) or 0) > 12_000_000:
        await m.answer(r["toobig"])
        return
    wait = await m.answer(r["wait"])
    try:
        buf = io.BytesIO()
        await bot.download(media, destination=buf)
        data = await gemini_extract(buf.getvalue(), mime, prompt=RECEIPT_PROMPT + script_hint(lang), kind="image")
        rec = build_receipt(data, date.fromisoformat(user["started_on"]), today())
    except Exception:
        log.exception("Chekni o'qishda xato")
        await wait.edit_text(r["fail"])
        return
    if not rec:
        await wait.edit_text(r["none"])
        return
    now = datetime.now(TZ).timestamp()
    for k in [k for k, x in PENDING.items() if now - x["ts"] > 3600]:
        PENDING.pop(k, None)
    pid = uuid.uuid4().hex[:8]
    PENDING[pid] = {"kind": "receipt", "uid": user["user_id"], "ts": now, **rec}
    text, kb = receipt_view(lang, pid)
    await wait.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("r:"))
async def cb_receipt(c: CallbackQuery):
    user = get_user(c.from_user.id)
    if not user:
        await c.answer()
        return
    lang = user["lang"]
    r, t = RT[lang], T[lang]
    _, action, pid = c.data.split(":", 2)
    p = PENDING.get(pid)
    if not p or p.get("kind") != "receipt" or p["uid"] != user["user_id"]:
        await c.message.edit_text(r["expired"])
        await c.answer()
        return
    PENDING.pop(pid, None)
    if action == "c":
        await c.message.edit_text(r["cancelled"])
        await c.answer()
        return
    if action == "i" and p["consistent"]:
        rows = [(i["name"] or r["chek"], i["uzs"]) for i in p["items"]]
    else:
        rows = [(p["store"] or r["chek"], p["total"])]
    d = p["day"]
    ids, lines = [], []
    for nm, amt in rows:
        cur = db.execute(
            "INSERT INTO expenses(user_id, day, name, amount) VALUES (?,?,?,?)",
            (user["user_id"], d.isoformat(), nm, amt),
        )
        ids.append(str(cur.lastrowid))
        lines.append(f"🛒 {esc(nm)} — <b>{fmt(amt, lang)}</b>")
    db.commit()
    day_total = sum_between(user["user_id"], d, d)
    mtd = sum_between(user["user_id"], d.replace(day=1), d)
    text = (
        f"{t['added']} · {d.strftime('%d.%m.%Y')}\n\n" + "\n".join(lines[:20])
        + (f"\n{r['more'].format(n=len(lines) - 20)}" if len(lines) > 20 else "")
        + "\n━━━━━━━━━━━━━━\n"
        f"{r['total']}: <b>{fmt(sum(a for _, a in rows), lang)}</b>\n"
        f"📅 {d.strftime('%d.%m')}: <b>{fmt(day_total, lang)}</b>\n"
        f"{t['month_so_far'].format(month=MONTHS[lang][d.month - 1])}: <b>{fmt(mtd, lang)}</b>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t["btn_cancel"], callback_data="del:" + ",".join(ids))]]
    )
    await c.message.edit_text(text, reply_markup=kb)
    await c.answer()


# ───────────────────────── Avtomatik hisobotlar ─────────────────────────
async def broadcast(bot: Bot, builder):
    for user in db.execute("SELECT * FROM users").fetchall():
        try:
            text = builder(user)
            if text:
                await bot.send_message(user["user_id"], text)
        except Exception as e:  # bot bloklangan bo'lishi mumkin
            log.warning("Yuborib bo'lmadi %s: %s", user["user_id"], e)
        await asyncio.sleep(0.05)


async def job_daily(bot: Bot):
    d = today()
    await broadcast(bot, lambda u: today_report(u["user_id"], u["lang"], d, auto=True))


async def job_monthly(bot: Bot):
    prev = today().replace(day=1) - timedelta(days=1)  # 1-noyabr 00:00 da -> oktabr
    await broadcast(bot, lambda u: month_report(u, prev.year, prev.month))


async def job_yearly(bot: Bot):
    y = today().year
    await broadcast(bot, lambda u: year_report(u, y))


async def main():
    token = BOT_TOKEN.strip()
    if not token or token == "BU_YERGA_TOKENNI_YOZING":
        raise SystemExit("BOT_TOKEN topilmadi. .env faylga (yoki hosting Variables bo'limiga) BOT_TOKEN=... yozing.")
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    sched = AsyncIOScheduler(timezone="Asia/Tashkent")
    sched.add_job(job_daily, CronTrigger(hour=23, minute=59, second=0), args=[bot])
    sched.add_job(job_monthly, CronTrigger(day=1, hour=0, minute=0, second=0), args=[bot])
    sched.add_job(job_yearly, CronTrigger(month=12, day=31, hour=23, minute=59, second=30), args=[bot])
    sched.start()

    log.info("Bot ishga tushdi")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
