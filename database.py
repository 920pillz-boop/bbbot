import aiosqlite
from config import DB_PATH, REF_PERCENT


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # WAL-режим: параллельные читатели не блокируют запись
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        # ── Оригинальные таблицы ──────────────────────────────────────────
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id       INTEGER UNIQUE NOT NULL,
                tg_username TEXT,
                language    TEXT DEFAULT 'ru',
                ref_by      INTEGER,
                balance     REAL DEFAULT 0,
                income      REAL DEFAULT 0,
                status      TEXT DEFAULT 'new',
                step        INTEGER DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS anketa (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id          INTEGER UNIQUE NOT NULL,
                full_name      TEXT,
                height         TEXT,
                weight         TEXT,
                phone_model    TEXT,
                socials        TEXT,
                location       TEXT,
                limits         TEXT,
                desired_income TEXT,
                experience     TEXT,
                goals          TEXT,
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ref_bonuses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_tg_id INTEGER NOT NULL,
                from_tg_id  INTEGER NOT NULL,
                amount      REAL NOT NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── НОВЫЕ таблицы ─────────────────────────────────────────────────

        # Справочник площадок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS platforms (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT UNIQUE NOT NULL,
                slug       TEXT UNIQUE NOT NULL,
                color_hex  TEXT DEFAULT '#888888',
                sort_order INTEGER DEFAULT 0,
                is_active  INTEGER DEFAULT 1
            )
        """)

        # Заполняем площадки по умолчанию
        default_platforms = [
            ("OnlyFans",   "onlyfans",   "#00AFF0", 1),
            ("Fansly",     "fansly",     "#9B59B6", 2),
            ("BongaCams",  "bongacams",  "#E74C3C", 3),
            ("Chaturbate", "chaturbate", "#F39C12", 4),
            ("Stripchat",  "stripchat",  "#E91E63", 5),
            ("MYM.fans",   "mymfans",    "#FF6B35", 6),
        ]
        for name, slug, color, order in default_platforms:
            await db.execute(
                "INSERT OR IGNORE INTO platforms (name, slug, color_hex, sort_order) VALUES (?,?,?,?)",
                (name, slug, color, order)
            )

        # Привязка модели к площадкам
        await db.execute("""
            CREATE TABLE IF NOT EXISTS model_platforms (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id       INTEGER NOT NULL,
                platform_id INTEGER NOT NULL,
                account_url TEXT,
                is_active   INTEGER DEFAULT 1,
                added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tg_id, platform_id),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id),
                FOREIGN KEY (platform_id) REFERENCES platforms(id)
            )
        """)

        # Ежедневный заработок
        await db.execute("""
            CREATE TABLE IF NOT EXISTS daily_earnings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id       INTEGER NOT NULL,
                platform_id INTEGER NOT NULL,
                date        TEXT NOT NULL,
                amount      REAL NOT NULL CHECK(amount >= 0),
                added_by    TEXT DEFAULT 'admin',
                note        TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tg_id, platform_id, date),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id),
                FOREIGN KEY (platform_id) REFERENCES platforms(id)
            )
        """)

        # ── Новые таблицы v2 ──────────────────────────────────────────────

        # История изменений статуса
        await db.execute("""
            CREATE TABLE IF NOT EXISTS status_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id      INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT,
                changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Заметки администратора
        await db.execute("""
            CREATE TABLE IF NOT EXISTS admin_notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id      INTEGER NOT NULL,
                note       TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Запросы на выплату
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payout_requests (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id      INTEGER NOT NULL,
                amount     REAL NOT NULL,
                status     TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Добавляем photo_file_id в anketa если колонки ещё нет
        try:
            await db.execute("ALTER TABLE anketa ADD COLUMN photo_file_id TEXT")
        except Exception:
            pass  # Колонка уже существует

        await db.commit()


# ─── USERS ────────────────────────────────────────────────────────────────────

async def get_user(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(tg_id: int, username: str | None, language: str = "ru", ref_by: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_id, tg_username, language, ref_by) VALUES (?,?,?,?)",
            (tg_id, username, language, ref_by)
        )
        await db.commit()


async def update_user(tg_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [tg_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {fields} WHERE tg_id=?", values)
        await db.commit()


# ─── ANKETA ───────────────────────────────────────────────────────────────────

async def get_anketa(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM anketa WHERE tg_id=?", (tg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def upsert_anketa(tg_id: int, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        exists = await (await db.execute(
            "SELECT 1 FROM anketa WHERE tg_id=?", (tg_id,)
        )).fetchone()
        if exists:
            if kwargs:
                fields = ", ".join(f"{k}=?" for k in kwargs)
                values = list(kwargs.values()) + [tg_id]
                await db.execute(f"UPDATE anketa SET {fields} WHERE tg_id=?", values)
        else:
            cols = "tg_id, " + ", ".join(kwargs.keys())
            placeholders = ", ".join(["?"] * (len(kwargs) + 1))
            await db.execute(
                f"INSERT INTO anketa ({cols}) VALUES ({placeholders})",
                [tg_id] + list(kwargs.values())
            )
        await db.commit()


# ─── REFERRALS ────────────────────────────────────────────────────────────────

async def get_referrals(tg_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE ref_by=?", (tg_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_ref_bonuses(tg_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ref_bonuses WHERE owner_tg_id=? ORDER BY created_at DESC LIMIT ?",
            (tg_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def add_ref_bonus(owner_tg_id: int, from_tg_id: int, amount: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ref_bonuses (owner_tg_id, from_tg_id, amount) VALUES (?,?,?)",
            (owner_tg_id, from_tg_id, amount)
        )
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE tg_id=?",
            (amount, owner_tg_id)
        )
        await db.commit()


# ─── ADMIN ────────────────────────────────────────────────────────────────────

async def get_all_users(status: str | None = None, offset: int = 0, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if status:
            async with db.execute(
                "SELECT u.*, a.full_name FROM users u "
                "LEFT JOIN anketa a ON a.tg_id = u.tg_id "
                "WHERE u.status=? ORDER BY u.created_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset)
            ) as cur:
                rows = await cur.fetchall()
        else:
            async with db.execute(
                "SELECT u.*, a.full_name FROM users u "
                "LEFT JOIN anketa a ON a.tg_id = u.tg_id "
                "ORDER BY u.created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ) as cur:
                rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def count_users(status: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        if status:
            async with db.execute("SELECT COUNT(*) FROM users WHERE status=?", (status,)) as cur:
                row = await cur.fetchone()
        else:
            async with db.execute("SELECT COUNT(*) FROM users") as cur:
                row = await cur.fetchone()
        return row[0] if row else 0


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        for status in ("reviewing", "approved", "rejected", "active", "new", "filling"):
            async with db.execute("SELECT COUNT(*) FROM users WHERE status=?", (status,)) as cur:
                row = await cur.fetchone()
                stats[status] = row[0] if row else 0
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
            stats["total"] = row[0] if row else 0
        return stats


# ─── НОВОЕ: PLATFORMS ─────────────────────────────────────────────────────────

async def get_all_platforms(only_active: bool = True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM platforms"
        if only_active:
            query += " WHERE is_active=1"
        query += " ORDER BY sort_order"
        async with db.execute(query) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_platform_by_id(platform_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM platforms WHERE id=?", (platform_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ─── НОВОЕ: MODEL_PLATFORMS ───────────────────────────────────────────────────

async def get_model_platforms(tg_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT mp.*, p.name as platform_name, p.color_hex, p.slug
            FROM model_platforms mp
            JOIN platforms p ON p.id = mp.platform_id
            WHERE mp.tg_id=? AND mp.is_active=1
            ORDER BY p.sort_order
        """, (tg_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_platforms_batch(tg_ids: list[int]) -> dict[int, list[str]]:
    """Returns {tg_id: [platform_name, ...]} for multiple users at once."""
    if not tg_ids:
        return {}
    placeholders = ",".join("?" for _ in tg_ids)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT mp.tg_id, p.name as platform_name "
            f"FROM model_platforms mp "
            f"JOIN platforms p ON p.id = mp.platform_id "
            f"WHERE mp.tg_id IN ({placeholders}) AND mp.is_active=1 "
            f"ORDER BY p.sort_order",
            tg_ids
        ) as cur:
            rows = await cur.fetchall()
    result: dict[int, list[str]] = {tid: [] for tid in tg_ids}
    for row in rows:
        result[row["tg_id"]].append(row["platform_name"])
    return result


async def set_model_platform(tg_id: int, platform_id: int, account_url: str = None, is_active: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO model_platforms (tg_id, platform_id, account_url, is_active)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tg_id, platform_id) DO UPDATE SET
                account_url=excluded.account_url,
                is_active=excluded.is_active
        """, (tg_id, platform_id, account_url, 1 if is_active else 0))
        await db.commit()


async def remove_model_platform(tg_id: int, platform_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE model_platforms SET is_active=0 WHERE tg_id=? AND platform_id=?",
            (tg_id, platform_id)
        )
        await db.commit()


# ─── НОВОЕ: DAILY_EARNINGS ────────────────────────────────────────────────────

async def upsert_earning(
    tg_id: int, platform_id: int, date: str,
    amount: float, added_by: str = "admin", note: str = None
):
    """Добавить или обновить заработок за день. Автоматически начисляет 5% рефереру."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем старую сумму (если есть) для расчёта дельты реф.бонуса
        async with db.execute(
            "SELECT amount FROM daily_earnings WHERE tg_id=? AND platform_id=? AND date=?",
            (tg_id, platform_id, date)
        ) as cur:
            old_row = await cur.fetchone()
        old_amount = float(old_row[0]) if old_row else 0.0

        await db.execute("""
            INSERT INTO daily_earnings (tg_id, platform_id, date, amount, added_by, note)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tg_id, platform_id, date) DO UPDATE SET
                amount=excluded.amount,
                added_by=excluded.added_by,
                note=excluded.note
        """, (tg_id, platform_id, date, amount, added_by, note))

        # Пересчитываем суммарный доход модели
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM daily_earnings WHERE tg_id=?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            total = float(row[0]) if row else 0.0
        await db.execute("UPDATE users SET income=? WHERE tg_id=?", (total, tg_id))

        # Авто реф.бонус 5% от дельты (чтобы не дублировать при обновлении)
        delta = amount - old_amount
        if delta > 0:
            async with db.execute("SELECT ref_by FROM users WHERE tg_id=?", (tg_id,)) as cur:
                user_row = await cur.fetchone()
            if user_row and user_row[0]:
                bonus = round(delta * REF_PERCENT / 100, 2)
                await db.execute(
                    "INSERT INTO ref_bonuses (owner_tg_id, from_tg_id, amount) VALUES (?,?,?)",
                    (user_row[0], tg_id, bonus)
                )
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE tg_id=?",
                    (bonus, user_row[0])
                )

        await db.commit()


async def get_earnings_for_month(tg_id: int, year: int, month: int) -> list[dict]:
    """Заработок модели за месяц — по дням и площадкам."""
    date_prefix = f"{year:04d}-{month:02d}-%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT de.date, de.amount, de.platform_id,
                   p.name as platform_name, p.color_hex, p.slug
            FROM daily_earnings de
            JOIN platforms p ON p.id = de.platform_id
            WHERE de.tg_id=? AND de.date LIKE ?
            ORDER BY de.date, p.sort_order
        """, (tg_id, date_prefix)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_monthly_total(tg_id: int, year: int, month: int) -> float:
    date_prefix = f"{year:04d}-{month:02d}-%"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM daily_earnings WHERE tg_id=? AND date LIKE ?",
            (tg_id, date_prefix)
        ) as cur:
            row = await cur.fetchone()
            return float(row[0]) if row else 0.0


async def get_all_models_monthly_stats(year: int, month: int) -> list[dict]:
    """Для админки: все активные модели со статистикой за месяц."""
    date_prefix = f"{year:04d}-{month:02d}-%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT
                u.tg_id, u.tg_username, u.status, u.ref_by,
                a.full_name,
                COALESCE(SUM(de.amount), 0) as month_total,
                COUNT(DISTINCT de.platform_id) as active_platforms
            FROM users u
            LEFT JOIN anketa a ON a.tg_id = u.tg_id
            LEFT JOIN daily_earnings de ON de.tg_id = u.tg_id AND de.date LIKE ?
            WHERE u.status IN ('active', 'approved')
            GROUP BY u.tg_id
            ORDER BY month_total DESC
        """, (date_prefix,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_earnings_by_platform_month(year: int, month: int) -> list[dict]:
    """Для админки: сводка по площадкам за месяц."""
    date_prefix = f"{year:04d}-{month:02d}-%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT p.name, p.color_hex, p.slug,
                   COUNT(DISTINCT de.tg_id) as models_count,
                   COALESCE(SUM(de.amount), 0) as total
            FROM platforms p
            LEFT JOIN daily_earnings de ON de.platform_id = p.id AND de.date LIKE ?
            WHERE p.is_active=1
            GROUP BY p.id
            ORDER BY total DESC
        """, (date_prefix,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_ref_bonuses_for_month(tg_id: int, year: int, month: int) -> list[dict]:
    """Реф.бонусы модели за месяц — сгруппированные по дням."""
    ym = f"{year:04d}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT date(created_at) as date, SUM(amount) as amount
            FROM ref_bonuses
            WHERE owner_tg_id=? AND strftime('%Y-%m', created_at)=?
            GROUP BY date(created_at)
            ORDER BY date(created_at)
        """, (tg_id, ym)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_monthly_ref_bonus_total(tg_id: int, year: int, month: int) -> float:
    """Итого реф.бонусов за месяц."""
    ym = f"{year:04d}-{month:02d}"
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM ref_bonuses
            WHERE owner_tg_id=? AND strftime('%Y-%m', created_at)=?
        """, (tg_id, ym)) as cur:
            row = await cur.fetchone()
            return float(row[0]) if row else 0.0


async def get_all_models_for_admin() -> list[dict]:
    """Все пользователи с анкетой — для списка в Admin Mini App."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.tg_id, u.tg_username, u.status, u.income, u.balance, u.ref_by,
                   a.full_name
            FROM users u
            LEFT JOIN anketa a ON a.tg_id = u.tg_id
            ORDER BY
                CASE u.status
                    WHEN 'active'    THEN 1
                    WHEN 'approved'  THEN 2
                    WHEN 'reviewing' THEN 3
                    WHEN 'new'       THEN 4
                    WHEN 'filling'   THEN 5
                    WHEN 'rejected'  THEN 6
                END,
                u.income DESC
        """) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── НОВОЕ v2: STATUS HISTORY ─────────────────────────────────────────────────

async def add_status_history(tg_id: int, old_status: str | None, new_status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO status_history (tg_id, old_status, new_status) VALUES (?,?,?)",
            (tg_id, old_status, new_status)
        )
        await db.commit()


async def get_status_history(tg_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM status_history WHERE tg_id=? ORDER BY changed_at DESC LIMIT ?",
            (tg_id, limit)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── НОВОЕ v2: ADMIN NOTES ────────────────────────────────────────────────────

async def add_admin_note(tg_id: int, note: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO admin_notes (tg_id, note) VALUES (?,?)",
            (tg_id, note)
        )
        await db.commit()


async def get_admin_notes(tg_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM admin_notes WHERE tg_id=? ORDER BY created_at DESC",
            (tg_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── НОВОЕ v2: PAYOUT REQUESTS ────────────────────────────────────────────────

async def create_payout_request(tg_id: int, amount: float) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO payout_requests (tg_id, amount) VALUES (?,?)",
            (tg_id, amount)
        )
        await db.commit()
        return cur.lastrowid


async def get_payout_requests(status: str = "pending") -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT pr.*, u.tg_username, a.full_name "
            "FROM payout_requests pr "
            "LEFT JOIN users u ON u.tg_id = pr.tg_id "
            "LEFT JOIN anketa a ON a.tg_id = pr.tg_id "
            "WHERE pr.status=? ORDER BY pr.created_at DESC",
            (status,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def update_payout_request(request_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payout_requests SET status=? WHERE id=?",
            (status, request_id)
        )
        await db.commit()


# ─── НОВОЕ v2: DELETE EARNING ─────────────────────────────────────────────────

async def delete_earning(tg_id: int, platform_id: int, date_str: str):
    """Удаляет запись о заработке и пересчитывает суммарный доход модели."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM daily_earnings WHERE tg_id=? AND platform_id=? AND date=?",
            (tg_id, platform_id, date_str)
        )
        # Пересчитываем суммарный доход
        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM daily_earnings WHERE tg_id=?", (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            total = float(row[0]) if row else 0.0
        await db.execute("UPDATE users SET income=? WHERE tg_id=?", (total, tg_id))
        await db.commit()


# ─── НОВОЕ v2: REVIEWING USERS OLDER THAN N HOURS ────────────────────────────

async def get_reviewing_users_older_than(hours: int = 24) -> list[dict]:
    """Пользователи со статусом 'reviewing', у которых анкета подана более N часов назад."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT u.tg_id, u.tg_username, u.created_at, a.full_name
            FROM users u
            LEFT JOIN anketa a ON a.tg_id = u.tg_id
            WHERE u.status = 'reviewing'
              AND u.created_at <= datetime('now', ? || ' hours')
        """, (f"-{hours}",)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


# ─── НОВОЕ v2: ALL ACTIVE MODELS FOR SUMMARY ─────────────────────────────────

async def get_all_active_models_for_summary() -> list[dict]:
    """Все активные модели — tg_id и язык — для рассылки итогов."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT tg_id, language FROM users WHERE status='active'",
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
