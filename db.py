"""
Вся работа с базой данных в одном месте.
База — обычный файл SQLite (fitbot.db), создаётся автоматически при первом запуске.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
from typing import Optional

DB_PATH = "fitbot.db"


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id INTEGER UNIQUE NOT NULL,
                role TEXT DEFAULT 'client',
                name TEXT,
                age INTEGER,
                goal TEXT,
                contact_method TEXT,
                contact_time TEXT,
                is_existing_client INTEGER DEFAULT 0,
                onboarded INTEGER DEFAULT 0,
                registered_at TEXT
            );

            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trainer_tg_id INTEGER,
                title TEXT,
                file_id TEXT,
                tags TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_tg_id INTEGER,
                week_start TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS plan_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id INTEGER REFERENCES plans(id) ON DELETE CASCADE,
                day_of_week INTEGER,
                exercise_id INTEGER REFERENCES exercises(id),
                sets_reps TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS nutrition_tips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS warmups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS weight_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_tg_id INTEGER,
                report_date TEXT,
                weight REAL,
                note TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS nutrition_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_tg_id INTEGER,
                report_date TEXT,
                description TEXT,
                photo_file_id TEXT,
                created_at TEXT
            );
            """
        )
        # Немного контента по умолчанию, чтобы кабинет не был пустым при первом запуске
        row = conn.execute("SELECT COUNT(*) c FROM warmups").fetchone()
        if row["c"] == 0:
            conn.execute(
                "INSERT INTO warmups (title, content, created_at) VALUES (?,?,?)",
                (
                    "Базовая разминка перед тренировкой",
                    "5 минут лёгкого кардио, суставная разминка сверху вниз, "
                    "10 приседаний без веса, 10 отжиманий от стены, растяжка основных групп мышц.",
                    datetime.utcnow().isoformat(),
                ),
            )
        row = conn.execute("SELECT COUNT(*) c FROM nutrition_tips").fetchone()
        if row["c"] == 0:
            conn.execute(
                "INSERT INTO nutrition_tips (title, content, created_at) VALUES (?,?,?)",
                (
                    "С чего начать",
                    "Пейте достаточно воды, старайтесь есть белок в каждый приём пищи, "
                    "не пропускайте завтрак. Подробные рекомендации добавит ваш тренер.",
                    datetime.utcnow().isoformat(),
                ),
            )


# ---------- users ----------

def upsert_user_start(tg_id: int, role: str = "client"):
    with get_db() as conn:
        existing = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        if existing:
            return dict(existing)
        conn.execute(
            "INSERT INTO users (tg_id, role, registered_at) VALUES (?,?,?)",
            (tg_id, role, datetime.utcnow().isoformat()),
        )
        row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        return dict(row)


def get_user(tg_id: int) -> Optional[dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)).fetchone()
        return dict(row) if row else None


def save_questionnaire(tg_id: int, name: str, age, goal: str,
                        is_existing_client: bool, contact_method: str, contact_time: str):
    with get_db() as conn:
        conn.execute(
            """UPDATE users SET name=?, age=?, goal=?, is_existing_client=?,
               contact_method=?, contact_time=?, onboarded=1 WHERE tg_id=?""",
            (name, age, goal, int(is_existing_client), contact_method, contact_time, tg_id),
        )


def list_clients():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE role='client' AND onboarded=1 ORDER BY registered_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- exercises (video library) ----------

def add_exercise(trainer_tg_id: int, title: str, file_id: str, tags: str = ""):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO exercises (trainer_tg_id, title, file_id, tags, created_at) VALUES (?,?,?,?,?)",
            (trainer_tg_id, title, file_id, tags, datetime.utcnow().isoformat()),
        )


def list_exercises(trainer_tg_id: int):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM exercises WHERE trainer_tg_id=? ORDER BY created_at DESC", (trainer_tg_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_exercise(exercise_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
        return dict(row) if row else None


def recommended_exercise_order(trainer_tg_id: int, client_tg_id: int):
    """
    Возвращает библиотеку упражнений тренера, отсортированную так, что
    выше — то, что этому клиенту либо никогда не давали, либо давали давнее всего.
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT e.*, (
                SELECT MAX(p.week_start) FROM plan_items pi
                JOIN plans p ON p.id = pi.plan_id
                WHERE pi.exercise_id = e.id AND p.client_tg_id = ?
            ) AS last_given
            FROM exercises e
            WHERE e.trainer_tg_id = ?
            ORDER BY (last_given IS NOT NULL), last_given ASC, e.created_at DESC
            """,
            (client_tg_id, trainer_tg_id),
        ).fetchall()
        return [dict(r) for r in rows]


# ---------- weekly plans ----------

def get_or_create_plan(client_tg_id: int, week_start: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM plans WHERE client_tg_id=? AND week_start=?", (client_tg_id, week_start)
        ).fetchone()
        if row:
            return dict(row)
        conn.execute(
            "INSERT INTO plans (client_tg_id, week_start, created_at) VALUES (?,?,?)",
            (client_tg_id, week_start, datetime.utcnow().isoformat()),
        )
        row = conn.execute(
            "SELECT * FROM plans WHERE client_tg_id=? AND week_start=?", (client_tg_id, week_start)
        ).fetchone()
        return dict(row)


def replace_plan_items(plan_id: int, items: list[dict]):
    """items: [{day_of_week, exercise_id, sets_reps, notes}, ...]"""
    with get_db() as conn:
        conn.execute("DELETE FROM plan_items WHERE plan_id=?", (plan_id,))
        for it in items:
            conn.execute(
                """INSERT INTO plan_items (plan_id, day_of_week, exercise_id, sets_reps, notes)
                   VALUES (?,?,?,?,?)""",
                (plan_id, it["day_of_week"], it["exercise_id"], it.get("sets_reps", ""), it.get("notes", "")),
            )


def get_plan_with_items(client_tg_id: int, week_start: str):
    with get_db() as conn:
        plan = conn.execute(
            "SELECT * FROM plans WHERE client_tg_id=? AND week_start=?", (client_tg_id, week_start)
        ).fetchone()
        if not plan:
            return None
        items = conn.execute(
            """SELECT pi.*, e.title, e.file_id, e.tags FROM plan_items pi
               JOIN exercises e ON e.id = pi.exercise_id
               WHERE pi.plan_id=? ORDER BY pi.day_of_week""",
            (plan["id"],),
        ).fetchall()
        result = dict(plan)
        result["items"] = [dict(i) for i in items]
        return result


# ---------- nutrition tips & warmups ----------

def list_nutrition_tips():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM nutrition_tips ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def list_warmups():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM warmups ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# ---------- reports ----------

def add_weight_report(client_tg_id: int, weight: float, note: str = "", report_date: str = None):
    report_date = report_date or date.today().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO weight_reports (client_tg_id, report_date, weight, note, created_at)
               VALUES (?,?,?,?,?)""",
            (client_tg_id, report_date, weight, note, datetime.utcnow().isoformat()),
        )


def list_weight_reports(client_tg_id: int, limit: int = 30):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM weight_reports WHERE client_tg_id=? ORDER BY report_date DESC LIMIT ?",
            (client_tg_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def add_nutrition_report(client_tg_id: int, description: str, photo_file_id: str = None, report_date: str = None):
    report_date = report_date or date.today().isoformat()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO nutrition_reports (client_tg_id, report_date, description, photo_file_id, created_at)
               VALUES (?,?,?,?,?)""",
            (client_tg_id, report_date, description, photo_file_id, datetime.utcnow().isoformat()),
        )


def list_nutrition_reports(client_tg_id: int, limit: int = 30):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM nutrition_reports WHERE client_tg_id=? ORDER BY report_date DESC LIMIT ?",
            (client_tg_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
