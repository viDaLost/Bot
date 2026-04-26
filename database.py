import aiosqlite
from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            chat_id TEXT NOT NULL,
            title TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            location_name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timezone TEXT NOT NULL,
            publish_date TEXT,
            publish_time TEXT NOT NULL,
            schedule_type TEXT DEFAULT 'once',
            weekdays TEXT DEFAULT '',
            month_day INTEGER,
            image_style TEXT DEFAULT 'classic',
            title_text TEXT DEFAULT 'Заход солнца',
            show_city INTEGER DEFAULT 0,
            show_weekday INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            last_sent_key TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(target_id) REFERENCES targets(id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS send_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            owner_id INTEGER NOT NULL,
            target_id INTEGER,
            status TEXT NOT NULL,
            target_date TEXT,
            sunset_time TEXT,
            error TEXT DEFAULT '',
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Миграции для старых bot.db.
        await _ensure_column(db, "jobs", "schedule_type", "TEXT DEFAULT 'once'")
        await _ensure_column(db, "jobs", "weekdays", "TEXT DEFAULT ''")
        await _ensure_column(db, "jobs", "month_day", "INTEGER")
        await _ensure_column(db, "jobs", "image_style", "TEXT DEFAULT 'classic'")
        await _ensure_column(db, "jobs", "title_text", "TEXT DEFAULT 'Заход солнца'")
        await _ensure_column(db, "jobs", "show_city", "INTEGER DEFAULT 0")
        await _ensure_column(db, "jobs", "show_weekday", "INTEGER DEFAULT 0")
        await _ensure_column(db, "jobs", "last_sent_key", "TEXT DEFAULT ''")

        await db.commit()


async def _ensure_column(db, table_name: str, column_name: str, definition: str):
    cur = await db.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in await cur.fetchall()]
    if column_name not in columns:
        await db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


async def add_target(owner_id: int, chat_id: str, title: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO targets(owner_id, chat_id, title) VALUES (?, ?, ?)",
            (owner_id, chat_id, title),
        )
        await db.commit()


async def get_targets(owner_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM targets WHERE owner_id = ? ORDER BY id DESC",
            (owner_id,),
        )
        return await cur.fetchall()


async def get_target_by_id(target_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
        return await cur.fetchone()


async def delete_target(target_id: int, owner_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM jobs WHERE target_id=? AND owner_id=?", (target_id, owner_id))
        await db.execute("DELETE FROM targets WHERE id=? AND owner_id=?", (target_id, owner_id))
        await db.commit()


async def add_job(
    owner_id: int,
    target_id: int,
    location_name: str,
    latitude: float,
    longitude: float,
    timezone: str,
    publish_time: str,
    schedule_type: str = "once",
    publish_date: str | None = None,
    weekdays: str = "",
    month_day: int | None = None,
    image_style: str = "classic",
    title_text: str = "Заход солнца",
    show_city: int = 0,
    show_weekday: int = 0,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO jobs(
                owner_id, target_id, location_name, latitude, longitude,
                timezone, publish_date, publish_time, schedule_type, weekdays,
                month_day, image_style, title_text, show_city, show_weekday
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_id,
                target_id,
                location_name,
                latitude,
                longitude,
                timezone,
                publish_date,
                publish_time,
                schedule_type,
                weekdays,
                month_day,
                image_style,
                title_text,
                show_city,
                show_weekday,
            ),
        )
        await db.commit()
        return int(cur.lastrowid)


async def get_job_by_id(job_id: int, owner_id: int | None = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if owner_id is None:
            cur = await db.execute(
                """
                SELECT jobs.*, targets.chat_id, targets.title AS target_title
                FROM jobs JOIN targets ON jobs.target_id = targets.id
                WHERE jobs.id=?
                """,
                (job_id,),
            )
        else:
            cur = await db.execute(
                """
                SELECT jobs.*, targets.chat_id, targets.title AS target_title
                FROM jobs JOIN targets ON jobs.target_id = targets.id
                WHERE jobs.id=? AND jobs.owner_id=?
                """,
                (job_id, owner_id),
            )
        return await cur.fetchone()


async def get_active_jobs():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT jobs.*, targets.chat_id, targets.title AS target_title
            FROM jobs JOIN targets ON jobs.target_id = targets.id
            WHERE jobs.status = 'active'
            ORDER BY jobs.id ASC
            """
        )
        return await cur.fetchall()


async def get_jobs(owner_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT jobs.*, targets.title AS target_title, targets.chat_id
            FROM jobs JOIN targets ON jobs.target_id = targets.id
            WHERE jobs.owner_id=?
            ORDER BY jobs.id DESC
            """,
            (owner_id,),
        )
        return await cur.fetchall()


async def update_job_fields(job_id: int, owner_id: int, **fields):
    allowed = {
        "publish_date", "publish_time", "schedule_type", "weekdays", "month_day",
        "image_style", "title_text", "show_city", "show_weekday", "status",
        "location_name", "latitude", "longitude", "timezone", "target_id",
    }
    clean = {k: v for k, v in fields.items() if k in allowed}
    if not clean:
        return
    assignments = ", ".join([f"{k}=?" for k in clean])
    values = list(clean.values()) + [job_id, owner_id]
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE jobs SET {assignments} WHERE id=? AND owner_id=?",
            values,
        )
        await db.commit()


async def delete_job(job_id: int, owner_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM jobs WHERE id=? AND owner_id=?", (job_id, owner_id))
        await db.commit()


async def mark_job_done(job_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE jobs SET status='done' WHERE id=?", (job_id,))
        await db.commit()


async def update_job_last_sent(job_id: int, sent_key: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE jobs SET last_sent_key=? WHERE id=?", (sent_key, job_id))
        await db.commit()


async def add_send_log(
    job_id: int | None,
    owner_id: int,
    target_id: int | None,
    status: str,
    target_date: str | None = None,
    sunset_time: str | None = None,
    error: str = "",
):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO send_logs(job_id, owner_id, target_id, status, target_date, sunset_time, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, owner_id, target_id, status, target_date, sunset_time, error),
        )
        await db.commit()


async def get_send_logs(owner_id: int, limit: int = 20):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT send_logs.*, jobs.location_name, targets.title AS target_title
            FROM send_logs
            LEFT JOIN jobs ON send_logs.job_id = jobs.id
            LEFT JOIN targets ON send_logs.target_id = targets.id
            WHERE send_logs.owner_id=?
            ORDER BY send_logs.id DESC
            LIMIT ?
            """,
            (owner_id, limit),
        )
        return await cur.fetchall()
