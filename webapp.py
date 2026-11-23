"""EasySpend Mini App: xavfsiz API (Telegram initData tekshiruvi bilan) va sahifalarni berish.

Bu modul main.py bilan bir jarayonda ishlaydi va bir xil SQLite bazadan foydalanadi.
"""
import hashlib
import hmac
import json
import os
import time
from calendar import monthrange
from datetime import date, datetime, timedelta
from urllib.parse import parse_qsl
from zoneinfo import ZoneInfo

from categories import CATS, categorize

BASE = os.path.dirname(os.path.abspath(__file__))
TZ = ZoneInfo("Asia/Tashkent")
MAX_AMOUNT = 10**12


def today() -> date:
    return datetime.now(TZ).date()


# ───────────────────────── Xavfsizlik: Telegram initData ─────────────────────────
def verify_init_data(init_data: str, token: str, max_age: int = 86400):
    """Telegram bergan initData haqiqiyligini tekshiradi. To'g'ri bo'lsa user dict, aks holda None."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = pairs.pop("hash", None)
        if not recv_hash:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            return None
        return json.loads(pairs["user"])
    except Exception:
        return None


# ───────────────────────── Ma'lumot yig'ish ─────────────────────────
def _month_range(ym: str):
    try:
        y, m = (int(x) for x in ym.split("-"))
        start = date(y, m, 1)
    except Exception:
        t = today()
        y, m, start = t.year, t.month, t.replace(day=1)
    end = date(y, m, monthrange(y, m)[1])
    return y, m, start, end


def _sum(db, table: str, uid: int, a: date, b: date) -> int:
    return db.execute(
        f"SELECT COALESCE(SUM(amount),0) FROM {table} WHERE user_id=? AND day BETWEEN ? AND ?",
        (uid, a.isoformat(), b.isoformat()),
    ).fetchone()[0]


def build_summary(db, user, ym: str | None) -> dict:
    uid = user["user_id"]
    t = today()
    y, m, start, end = _month_range(ym or t.strftime("%Y-%m"))
    monday = t - timedelta(days=t.weekday())

    cats = db.execute(
        "SELECT COALESCE(category,'other') c, SUM(amount) s, COUNT(*) n FROM expenses "
        "WHERE user_id=? AND day BETWEEN ? AND ? GROUP BY c ORDER BY s DESC",
        (uid, start.isoformat(), end.isoformat()),
    ).fetchall()
    per_day = {
        r["day"]: r["s"]
        for r in db.execute(
            "SELECT day, SUM(amount) s FROM expenses WHERE user_id=? AND day BETWEEN ? AND ? GROUP BY day",
            (uid, start.isoformat(), end.isoformat()),
        )
    }
    days = []
    d = start
    while d <= end:
        days.append({"day": d.isoformat(), "sum": per_day.get(d.isoformat(), 0)})
        d += timedelta(days=1)

    expenses = [
        {"id": r["id"], "day": r["day"], "name": r["name"], "amount": r["amount"], "category": r["category"] or "other"}
        for r in db.execute(
            "SELECT id, day, name, amount, category FROM expenses WHERE user_id=? AND day BETWEEN ? AND ? "
            "ORDER BY day DESC, id DESC LIMIT 1000",
            (uid, start.isoformat(), end.isoformat()),
        )
    ]
    incomes = [
        {"id": r["id"], "day": r["day"], "name": r["name"], "amount": r["amount"]}
        for r in db.execute(
            "SELECT id, day, name, amount FROM incomes WHERE user_id=? AND day BETWEEN ? AND ? "
            "ORDER BY day DESC, id DESC LIMIT 500",
            (uid, start.isoformat(), end.isoformat()),
        )
    ]
    recurring = [
        {"id": r["id"], "name": r["name"], "amount": r["amount"], "category": r["category"] or "other", "dom": r["dom"]}
        for r in db.execute("SELECT * FROM recurring WHERE user_id=? ORDER BY dom, id", (uid,))
    ]
    spent = sum(c["s"] for c in cats)
    income = _sum(db, "incomes", uid, start, end)
    return {
        "user": {
            "name": user["first_name"],
            "lang": user["lang"],
            "budget": user["budget"] or 0,
        },
        "month": f"{y:04d}-{m:02d}",
        "today": t.isoformat(),
        "is_current": start <= t <= end,
        "today_sum": _sum(db, "expenses", uid, t, t),
        "week_sum": _sum(db, "expenses", uid, monday, t),
        "spent": spent,
        "income": income,
        "balance": income - spent,
        "by_category": [{"cat": c["c"] if c["c"] in CATS else "other", "sum": c["s"], "n": c["n"]} for c in cats],
        "by_day": days,
        "expenses": expenses,
        "incomes": incomes,
        "recurring": recurring,
    }


# ───────────────────────── Amallar (qo'shish / o'zgartirish / o'chirish) ─────────────────────────
class ApiError(Exception):
    pass


def _amount(v) -> int:
    try:
        n = int(round(float(v)))
    except Exception:
        raise ApiError("bad_amount")
    if not (1 <= n <= MAX_AMOUNT):
        raise ApiError("bad_amount")
    return n


def _name(v, limit=100) -> str:
    return str(v or "").strip()[:limit]


def _day(v) -> str:
    if not v:
        return today().isoformat()
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except Exception:
        raise ApiError("bad_date")


def _cat(v, name: str) -> str:
    if v in CATS:
        return v
    return categorize(name)


def _id(v) -> int:
    try:
        return int(v)
    except Exception:
        raise ApiError("bad_id")


def do_action(db, uid: int, action: str, b: dict) -> None:
    if action == "expense_add":
        name = _name(b.get("name"))
        db.execute(
            "INSERT INTO expenses(user_id, day, name, amount, category) VALUES (?,?,?,?,?)",
            (uid, _day(b.get("day")), name, _amount(b.get("amount")), _cat(b.get("category"), name)),
        )
    elif action == "expense_update":
        name = _name(b.get("name"))
        db.execute(
            "UPDATE expenses SET day=?, name=?, amount=?, category=? WHERE id=? AND user_id=?",
            (_day(b.get("day")), name, _amount(b.get("amount")), _cat(b.get("category"), name), _id(b.get("id")), uid),
        )
    elif action == "expense_delete":
        db.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (_id(b.get("id")), uid))
    elif action == "income_add":
        db.execute(
            "INSERT INTO incomes(user_id, day, name, amount) VALUES (?,?,?,?)",
            (uid, _day(b.get("day")), _name(b.get("name")), _amount(b.get("amount"))),
        )
    elif action == "income_delete":
        db.execute("DELETE FROM incomes WHERE id=? AND user_id=?", (_id(b.get("id")), uid))
    elif action == "budget_set":
        try:
            val = int(round(float(b.get("budget") or 0)))
        except Exception:
            raise ApiError("bad_amount")
        if not (0 <= val <= MAX_AMOUNT):
            raise ApiError("bad_amount")
        db.execute("UPDATE users SET budget=?, budget_flag=NULL WHERE user_id=?", (val, uid))
    elif action == "recurring_add":
        name = _name(b.get("name"))
        if not name:
            raise ApiError("bad_name")
        try:
            dom = int(b.get("dom"))
        except Exception:
            raise ApiError("bad_day")
        if not (1 <= dom <= 31):
            raise ApiError("bad_day")
        db.execute(
            "INSERT INTO recurring(user_id, name, amount, category, dom) VALUES (?,?,?,?,?)",
            (uid, name, _amount(b.get("amount")), _cat(b.get("category"), name), dom),
        )
    elif action == "recurring_delete":
        db.execute("DELETE FROM recurring WHERE id=? AND user_id=?", (_id(b.get("id")), uid))
    elif action == "lang_set":
        lang = b.get("lang")
        if lang not in ("uz", "uzc", "ru", "en"):
            raise ApiError("bad_lang")
        db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))
    else:
        raise ApiError("unknown_action")
    db.commit()


# ───────────────────────── aiohttp ilovasi ─────────────────────────
def create_app(db, token: str):
    from aiohttp import web

    @web.middleware
    async def auth_mw(request, handler):
        if request.path.startswith("/api/"):
            info = verify_init_data(request.headers.get("X-Init-Data", ""), token)
            if not info:
                return web.json_response({"error": "unauthorized"}, status=401)
            user = db.execute("SELECT * FROM users WHERE user_id=?", (info["id"],)).fetchone()
            if not user:
                return web.json_response({"error": "not_registered"}, status=403)
            request["user"] = user
            db.execute("INSERT OR IGNORE INTO activity(user_id, day) VALUES (?,?)", (user["user_id"], today().isoformat()))
            db.commit()
        return await handler(request)

    async def read_json(request) -> dict:
        try:
            data = await request.json()
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    async def api_init(request):
        body = await read_json(request)
        return web.json_response(build_summary(db, request["user"], body.get("month")))

    async def api_action(request):
        action = request.match_info["action"]
        body = await read_json(request)
        try:
            do_action(db, request["user"]["user_id"], action, body)
        except ApiError as e:
            return web.json_response({"error": str(e)}, status=400)
        return web.json_response({"ok": True})

    def static(name: str):
        async def handler(request):
            return web.FileResponse(os.path.join(BASE, name), headers={"Cache-Control": "no-cache"})
        return handler

    async def health(request):
        return web.Response(text="ok")

    app = web.Application(middlewares=[auth_mw])
    app.router.add_get("/", static("index.html"))
    app.router.add_get("/style.css", static("style.css"))
    app.router.add_get("/app.js", static("app.js"))
    app.router.add_get("/health", health)
    app.router.add_post("/api/init", api_init)
    app.router.add_post("/api/{action}", api_action)
    return app
