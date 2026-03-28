"""
web_server.py
─────────────
aiohttp-сервер для Telegram Mini App.
Раздаёт статику (webapp/) и REST API.
Запускается параллельно с ботом из bot.py.
"""

import csv
import hashlib
import hmac
import io
import json
import logging
import os
import time
from datetime import datetime
from urllib.parse import unquote, urlencode

from aiohttp import web

import database as db
from config import BOT_TOKEN, ADMIN_CHAT_ID, WEBAPP_PORT, MINIAPP_URL

logger = logging.getLogger(__name__)

WEBAPP_DIR = os.path.join(os.path.dirname(__file__), "webapp")


# ─── AUTH: валидация Telegram initData ───────────────────────────────────────

def validate_init_data(init_data: str) -> dict | None:
    """
    Проверяет подпись initData от Telegram WebApp.
    Возвращает dict с данными пользователя или None если невалидно.
    """
    try:
        # Парсим НЕ декодируя всю строку — значения декодируем по отдельности
        pairs = {}
        for part in init_data.split("&"):
            key, _, val = part.partition("=")
            pairs[key] = unquote(val)
    except Exception:
        return None

    check_hash = pairs.pop("hash", None)
    if not check_hash:
        logger.warning("initData: no hash field")
        return None

    # data-check-string: отсортированные key=value через \n
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(pairs.items())
    )

    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, check_hash):
        logger.warning("initData: hash mismatch")
        return None

    user_data = pairs.get("user")
    if user_data:
        return json.loads(user_data)
    return None


def generate_signed_url(tg_id: int, username: str = "", is_admin: bool = False) -> str:
    """Генерирует подписанную ссылку для открытия Mini App.
    Если задан MINIAPP_URL (GitHub Pages) — открывает там, передавая api= параметром.
    Иначе открывает прямо с Railway."""
    api_url = os.environ.get("WEBAPP_URL", "https://localhost:8080")
    miniapp_url = os.environ.get("MINIAPP_URL", "").rstrip("/")
    base_url = miniapp_url if miniapp_url else api_url
    ts = str(int(time.time()))
    data = f"{tg_id}:{username}:{1 if is_admin else 0}:{ts}"
    sig = hmac.new(BOT_TOKEN.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
    params = {"tg_id": tg_id, "user": username, "adm": 1 if is_admin else 0, "ts": ts, "sig": sig}
    if miniapp_url:
        params["api"] = api_url  # HTML на GitHub Pages делает запросы на Railway
    return f"{base_url}/?{urlencode(params)}"


def validate_signed_url(tg_id: int, username: str, adm: int, ts: str, sig: str) -> bool:
    """Проверяет подпись URL."""
    data = f"{tg_id}:{username}:{adm}:{ts}"
    expected = hmac.new(BOT_TOKEN.encode(), data.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(expected, sig):
        return False
    # Ссылка валидна 24 часа
    try:
        if abs(time.time() - int(ts)) > 86400:
            return False
    except ValueError:
        return False
    return True


def get_user_from_request(request: web.Request) -> dict | None:
    """Извлекает пользователя из Authorization header ИЛИ из подписанных query-параметров."""
    # 1. Пробуем initData из Authorization header
    auth = request.headers.get("Authorization", "")
    if auth:
        result = validate_init_data(auth)
        if result:
            return result

    # 2. Пробуем подписанные параметры из query/header
    tg_id = request.headers.get("X-TG-ID") or request.query.get("tg_id_auth")
    username = request.headers.get("X-TG-User") or request.query.get("user_auth") or ""
    adm = request.headers.get("X-TG-Admin") or request.query.get("adm_auth") or "0"
    ts = request.headers.get("X-TG-TS") or request.query.get("ts_auth") or ""
    sig = request.headers.get("X-TG-Sig") or request.query.get("sig_auth") or ""

    if tg_id and ts and sig:
        try:
            tg_id_int = int(tg_id)
            adm_int = int(adm)
        except ValueError:
            return None
        if validate_signed_url(tg_id_int, username, adm_int, ts, sig):
            return {"id": tg_id_int, "username": username, "is_admin_flag": adm_int}

    return None


def is_admin_user(user: dict) -> bool:
    return user.get("id") == ADMIN_CHAT_ID or user.get("is_admin_flag") == 1


# ─── MIDDLEWARE ──────────────────────────────────────────────────────────────

@web.middleware
async def cors_middleware(request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=200)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, X-TG-ID, X-TG-User, X-TG-Admin, X-TG-TS, X-TG-Sig"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


# ─── API: профиль ───────────────────────────────────────────────────────────

async def api_me(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)

    tg_id = tg_user["id"]
    user = await db.get_user(tg_id)
    if not user:
        return web.json_response({"error": "not_found"}, status=404)

    anketa = await db.get_anketa(tg_id) or {}
    platforms = await db.get_model_platforms(tg_id)

    return web.json_response({
        "user": {
            "tg_id": user["tg_id"],
            "username": user.get("tg_username"),
            "status": user["status"],
            "income": user.get("income", 0),
            "balance": user.get("balance", 0),
        },
        "anketa": {
            "full_name": anketa.get("full_name"),
            "height": anketa.get("height"),
            "weight": anketa.get("weight"),
            "phone_model": anketa.get("phone_model"),
            "socials": anketa.get("socials"),
            "location": anketa.get("location"),
            "limits": anketa.get("limits"),
            "desired_income": anketa.get("desired_income"),
            "experience": anketa.get("experience"),
            "goals": anketa.get("goals"),
        },
        "platforms": [
            {"id": p["platform_id"], "name": p["platform_name"], "slug": p["slug"], "color": p["color_hex"]}
            for p in platforms
        ],
        "is_admin": is_admin_user(tg_user),
    })


# ─── API: площадки ──────────────────────────────────────────────────────────

async def api_platforms(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)

    all_plats = await db.get_all_platforms()
    my_plats = await db.get_model_platforms(tg_user["id"])
    my_ids = {p["platform_id"] for p in my_plats}

    return web.json_response({
        "platforms": [
            {
                "id": p["id"], "name": p["name"], "slug": p["slug"],
                "color": p["color_hex"], "active": p["id"] in my_ids,
            }
            for p in all_plats
        ]
    })


async def api_toggle_platform(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)

    body = await request.json()
    platform_id = body.get("platform_id")
    if not platform_id:
        return web.json_response({"error": "missing platform_id"}, status=400)

    tg_id = tg_user["id"]
    my_plats = await db.get_model_platforms(tg_id)
    my_ids = {p["platform_id"] for p in my_plats}

    if platform_id in my_ids:
        await db.remove_model_platform(tg_id, platform_id)
    else:
        await db.set_model_platform(tg_id, platform_id)

    return web.json_response({"ok": True})


# ─── API: заработок (модель) ────────────────────────────────────────────────

async def api_earnings(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)

    year = int(request.match_info["year"])
    month = int(request.match_info["month"])
    tg_id = tg_user["id"]

    # Админ может смотреть чужие
    target_id = int(request.query.get("tg_id", tg_id))
    if target_id != tg_id and not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    earnings = await db.get_earnings_for_month(target_id, year, month)
    total = await db.get_monthly_total(target_id, year, month)
    ref_bonuses_list = await db.get_ref_bonuses_for_month(target_id, year, month)
    ref_total = await db.get_monthly_ref_bonus_total(target_id, year, month)

    # Прошлый месяц для сравнения
    pm, py = (month - 1, year) if month > 1 else (12, year - 1)
    prev_total = await db.get_monthly_total(target_id, py, pm)

    return web.json_response({
        "year": year, "month": month,
        "total": total + ref_total,
        "prev_total": prev_total,
        "ref_total": ref_total,
        # {date: amount} — для сетки
        "ref_bonuses": {r["date"]: r["amount"] for r in ref_bonuses_list},
        "entries": [
            {
                "date": e["date"],
                "amount": e["amount"],
                "platform": e["platform_name"],
                "platform_id": e["platform_id"],
                "color": e["color_hex"],
            }
            for e in earnings
        ],
    })


# ─── API: админ — все модели ────────────────────────────────────────────────

async def api_admin_stats(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    year = int(request.match_info["year"])
    month = int(request.match_info["month"])

    models = await db.get_all_models_monthly_stats(year, month)
    plats = await db.get_earnings_by_platform_month(year, month)

    return web.json_response({
        "year": year, "month": month,
        "grand_total": sum(m["month_total"] for m in models),
        "models": [
            {
                "tg_id": m["tg_id"],
                "username": m.get("tg_username"),
                "full_name": m.get("full_name"),
                "status": m["status"],
                "month_total": m["month_total"],
                "has_ref": bool(m.get("ref_by")),
            }
            for m in models
        ],
        "platforms": [
            {
                "name": p["name"], "total": p["total"],
                "models_count": p["models_count"], "color": p["color_hex"],
            }
            for p in plats
        ],
    })


# ─── API: админ — внести заработок ──────────────────────────────────────────

async def api_admin_add_earning(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    body = await request.json()
    tg_id = body.get("tg_id")
    platform_id = body.get("platform_id")
    date_str = body.get("date")
    amount = body.get("amount")

    if not all([tg_id, platform_id, date_str, amount is not None]):
        return web.json_response({"error": "missing fields"}, status=400)

    try:
        amount = float(amount)
        if amount < 0:
            raise ValueError
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid amount"}, status=400)

    # Валидация даты
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return web.json_response({"error": "invalid date, use YYYY-MM-DD"}, status=400)

    await db.upsert_earning(tg_id, platform_id, date_str, amount, added_by="admin")

    # Уведомить модель через бота (bot передаётся в app при старте)
    bot = request.app.get("bot")
    if bot:
        platform = await db.get_platform_by_id(platform_id)
        plat_name = (platform or {}).get("name", "")
        display_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
        try:
            await bot.send_message(
                tg_id,
                f"<b>+${amount:.2f}</b>\n"
                f"{display_date}  |  {plat_name}"
            )
        except Exception as e:
            logger.warning(f"Cannot notify model {tg_id}: {e}")

    return web.json_response({"ok": True})


# ─── API: админ — список всех моделей ───────────────────────────────────────

async def api_admin_models_list(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    models = await db.get_all_models_for_admin()
    tg_ids = [m["tg_id"] for m in models]
    plats_map = await db.get_platforms_batch(tg_ids)
    result = []
    for m in models:
        name = m.get("full_name") or m.get("tg_username") or str(m["tg_id"])
        result.append({
            "tg_id": m["tg_id"],
            "name": name,
            "username": m.get("tg_username"),
            "status": m["status"],
            "income": m.get("income", 0),
            "balance": m.get("balance", 0),
            "has_ref": bool(m.get("ref_by")),
            "platforms": plats_map.get(m["tg_id"], []),
        })

    return web.json_response({"models": result})


# ─── API: админ — детали модели ──────────────────────────────────────────────

async def api_admin_model_detail(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    target_id = int(request.match_info["tg_id"])
    user = await db.get_user(target_id)
    if not user:
        return web.json_response({"error": "not_found"}, status=404)

    anketa = await db.get_anketa(target_id) or {}
    all_platforms = await db.get_all_platforms()
    model_plats = await db.get_model_platforms(target_id)
    assigned_ids = {p["platform_id"] for p in model_plats}

    return web.json_response({
        "user": {
            "tg_id": user["tg_id"],
            "username": user.get("tg_username"),
            "status": user["status"],
            "income": user.get("income", 0),
            "balance": user.get("balance", 0),
            "ref_by": user.get("ref_by"),
        },
        "anketa": {k: anketa.get(k) for k in [
            "full_name", "height", "weight", "phone_model",
            "socials", "location", "limits", "desired_income", "experience", "goals"
        ]},
        "platforms": [
            {
                "id": p["id"], "name": p["name"], "slug": p["slug"],
                "color": p["color_hex"], "assigned": p["id"] in assigned_ids,
            }
            for p in all_platforms
        ],
    })


# ─── API: админ — назначить/снять площадку модели ───────────────────────────

async def api_admin_assign_platform(request: web.Request) -> web.Response:
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    body = await request.json()
    tg_id = body.get("tg_id")
    platform_id = body.get("platform_id")
    if not tg_id or not platform_id:
        return web.json_response({"error": "missing fields"}, status=400)

    plats = await db.get_model_platforms(tg_id)
    assigned_ids = {p["platform_id"] for p in plats}

    if platform_id in assigned_ids:
        await db.remove_model_platform(tg_id, platform_id)
    else:
        await db.set_model_platform(tg_id, platform_id)

    return web.json_response({"ok": True})


# ─── API NEW: экспорт CSV ────────────────────────────────────────────────────

async def api_export_earnings_csv(request: web.Request) -> web.Response:
    """GET /api/export/earnings/{year}/{month} — CSV для скачивания."""
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    year = int(request.match_info["year"])
    month = int(request.match_info["month"])

    models = await db.get_all_models_monthly_stats(year, month)
    tg_ids = [m["tg_id"] for m in models]
    plats_map = await db.get_platforms_batch(tg_ids)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["tg_id", "username", "full_name", "status", "month_total", "platforms"])

    for m in models:
        plat_names = "; ".join(plats_map.get(m["tg_id"], []))
        writer.writerow([
            m["tg_id"],
            m.get("tg_username") or "",
            m.get("full_name") or "",
            m.get("status") or "",
            f"{m['month_total']:.2f}",
            plat_names,
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename = f"earnings_{year}_{month:02d}.csv"
    return web.Response(
        body=csv_bytes,
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# ─── API NEW: отмена/удаление заработка ─────────────────────────────────────

async def api_admin_cancel_earning(request: web.Request) -> web.Response:
    """POST /api/admin/cancel-earning  body: {tg_id, platform_id, date}"""
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    body = await request.json()
    tg_id = body.get("tg_id")
    platform_id = body.get("platform_id")
    date_str = body.get("date")

    if not all([tg_id, platform_id, date_str]):
        return web.json_response({"error": "missing fields"}, status=400)

    await db.delete_earning(int(tg_id), int(platform_id), date_str)

    # Уведомить модель
    bot = request.app.get("bot")
    if bot:
        try:
            platform = await db.get_platform_by_id(int(platform_id))
            plat_name = (platform or {}).get("name", str(platform_id))
            display_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
            await bot.send_message(
                int(tg_id),
                f"ℹ️ Запись о заработке за <b>{display_date}</b> ({plat_name}) была отменена администратором."
            )
        except Exception as e:
            logger.warning(f"Cannot notify model {tg_id} about earning cancellation: {e}")

    return web.json_response({"ok": True})


# ─── API NEW: заметки администратора ─────────────────────────────────────────

async def api_admin_notes_get(request: web.Request) -> web.Response:
    """GET /api/admin/notes/{tg_id}"""
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    target_id = int(request.match_info["tg_id"])
    notes = await db.get_admin_notes(target_id)
    return web.json_response({
        "notes": [
            {"id": n["id"], "note": n["note"], "created_at": n["created_at"]}
            for n in notes
        ]
    })


async def api_admin_notes_post(request: web.Request) -> web.Response:
    """POST /api/admin/notes/{tg_id}  body: {note}"""
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    target_id = int(request.match_info["tg_id"])
    body = await request.json()
    note_text = body.get("note", "").strip()
    if not note_text:
        return web.json_response({"error": "note is empty"}, status=400)

    await db.add_admin_note(target_id, note_text)
    return web.json_response({"ok": True})


# ─── API NEW: рассылка ───────────────────────────────────────────────────────

async def api_admin_broadcast(request: web.Request) -> web.Response:
    """POST /api/admin/broadcast  body: {message}"""
    tg_user = get_user_from_request(request)
    if not tg_user or not is_admin_user(tg_user):
        return web.json_response({"error": "forbidden"}, status=403)

    body = await request.json()
    text = body.get("message", "").strip()
    if not text:
        return web.json_response({"error": "message is empty"}, status=400)

    bot = request.app.get("bot")
    if not bot:
        return web.json_response({"error": "bot not available"}, status=503)

    models = await db.get_all_active_models_for_summary()
    count = 0
    for m in models:
        try:
            await bot.send_message(m["tg_id"], text)
            count += 1
        except Exception as e:
            logger.warning(f"Broadcast failed for {m['tg_id']}: {e}")

    return web.json_response({"ok": True, "sent": count})


# ─── STATIC FILES ───────────────────────────────────────────────────────────

async def serve_index(request: web.Request) -> web.Response:
    index_path = os.path.join(WEBAPP_DIR, "index.html")
    return web.FileResponse(index_path)


# ─── APP FACTORY ─────────────────────────────────────────────────────────────

def create_app(bot=None) -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    if bot:
        app["bot"] = bot

    # API routes — existing
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/platforms", api_platforms)
    app.router.add_post("/api/toggle-platform", api_toggle_platform)
    app.router.add_get("/api/earnings/{year}/{month}", api_earnings)
    app.router.add_get("/api/admin/stats/{year}/{month}", api_admin_stats)
    app.router.add_post("/api/admin/add-earning", api_admin_add_earning)
    app.router.add_get("/api/admin/models", api_admin_models_list)
    app.router.add_get("/api/admin/model/{tg_id}", api_admin_model_detail)
    app.router.add_post("/api/admin/assign-platform", api_admin_assign_platform)

    # API routes — new
    app.router.add_get("/api/export/earnings/{year}/{month}", api_export_earnings_csv)
    app.router.add_post("/api/admin/cancel-earning", api_admin_cancel_earning)
    app.router.add_get("/api/admin/notes/{tg_id}", api_admin_notes_get)
    app.router.add_post("/api/admin/notes/{tg_id}", api_admin_notes_post)
    app.router.add_post("/api/admin/broadcast", api_admin_broadcast)

    # Static
    app.router.add_get("/", serve_index)
    app.router.add_static("/static/", path=WEBAPP_DIR, name="static")

    return app


async def start_web_server(bot=None):
    app = create_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEBAPP_PORT)
    await site.start()
    logger.info(f"Web server started on port {WEBAPP_PORT}")
    return runner
