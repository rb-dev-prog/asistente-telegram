from typing import List, Dict, Any, Optional
from database.connection import get_db_connection

# --- NOTAS ---

async def create_note(user_id: int, content: str, category: str = "general") -> int:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "INSERT INTO notes (user_id, content, category) VALUES (?, ?, ?)",
            (user_id, content, category)
        )
        await db.commit()
        return cursor.lastrowid

async def list_notes(user_id: int, category: Optional[str] = None) -> List[Dict[str, Any]]:
    async with get_db_connection() as db:
        db.row_factory = aiosqlite_row_to_dict
        if category and category.lower() != "todas":
            cursor = await db.execute(
                "SELECT id, content, category, created_at FROM notes WHERE user_id = ? AND category = ? ORDER BY id DESC",
                (user_id, category)
            )
        else:
            cursor = await db.execute(
                "SELECT id, content, category, created_at FROM notes WHERE user_id = ? ORDER BY id DESC",
                (user_id,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def delete_note(user_id: int, note_id: int) -> bool:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0

async def update_note(user_id: int, note_id: int, new_content: str) -> bool:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "UPDATE notes SET content = ? WHERE id = ? AND user_id = ?",
            (new_content, note_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0

# --- RECORDATORIOS ---

async def create_reminder(user_id: int, message: str, remind_at_iso: str) -> int:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "INSERT INTO reminders (user_id, message, remind_at) VALUES (?, ?, ?)",
            (user_id, message, remind_at_iso)
        )
        await db.commit()
        return cursor.lastrowid

async def get_pending_reminders(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    async with get_db_connection() as db:
        db.row_factory = aiosqlite_row_to_dict
        if user_id:
            cursor = await db.execute(
                "SELECT id, user_id, message, remind_at FROM reminders WHERE user_id = ? AND is_completed = 0 ORDER BY remind_at ASC",
                (user_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT id, user_id, message, remind_at FROM reminders WHERE is_completed = 0 ORDER BY remind_at ASC"
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def mark_reminder_completed(reminder_id: int) -> bool:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "UPDATE reminders SET is_completed = 1 WHERE id = ?",
            (reminder_id,)
        )
        await db.commit()
        return cursor.rowcount > 0

# --- EVENTOS / AGENDA ---

async def create_event(user_id: int, title: str, start_time_iso: str, end_time_iso: Optional[str] = None) -> int:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "INSERT INTO events (user_id, title, start_time, end_time) VALUES (?, ?, ?, ?)",
            (user_id, title, start_time_iso, end_time_iso)
        )
        await db.commit()
        return cursor.lastrowid

async def list_events(user_id: int, date_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    async with get_db_connection() as db:
        db.row_factory = aiosqlite_row_to_dict
        if date_prefix:
            cursor = await db.execute(
                "SELECT id, title, start_time, end_time FROM events WHERE user_id = ? AND start_time LIKE ? ORDER BY start_time ASC",
                (user_id, f"{date_prefix}%")
            )
        else:
            cursor = await db.execute(
                "SELECT id, title, start_time, end_time FROM events WHERE user_id = ? ORDER BY start_time ASC",
                (user_id,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def delete_event(user_id: int, event_id: int) -> bool:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "DELETE FROM events WHERE id = ? AND user_id = ?",
            (event_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0

async def delete_reminder(user_id: int, reminder_id: int) -> bool:
    async with get_db_connection() as db:
        cursor = await db.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        )
        await db.commit()
        return cursor.rowcount > 0

def aiosqlite_row_to_dict(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
