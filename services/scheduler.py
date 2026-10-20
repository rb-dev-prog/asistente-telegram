import logging
from typing import Optional
from datetime import datetime, timezone
import zoneinfo
from telegram.ext import Application, ContextTypes
from database.repository import get_pending_reminders, mark_reminder_completed
from config.settings import TIMEZONE

logger = logging.getLogger(__name__)

_active_app: Optional[Application] = None

def set_active_app(app: Application) -> None:
    global _active_app
    _active_app = app

def get_active_app() -> Optional[Application]:
    return _active_app

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    if not job or not job.data:
        return
    
    data = job.data
    user_id = data["user_id"]
    reminder_id = data["reminder_id"]
    message = data["message"]
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ *¡Recordatorio!*\n\n📌 {message}",
            parse_mode="Markdown"
        )
        await mark_reminder_completed(reminder_id)
        logger.info(f"Recordatorio {reminder_id} enviado exitosamente a usuario {user_id}")
    except Exception as e:
        logger.error(f"Error al enviar recordatorio {reminder_id}: {e}")

def schedule_reminder_job(app: Application, reminder_id: int, user_id: int, message: str, remind_at_dt: datetime) -> None:
    if not app.job_queue:
        logger.warning("JobQueue no está disponible en la aplicación.")
        return
    
    try:
        tz = zoneinfo.ZoneInfo(TIMEZONE)
    except Exception:
        tz = timezone.utc
    
    now = datetime.now(tz)
    
    if remind_at_dt.tzinfo is None:
        remind_at_dt = remind_at_dt.replace(tzinfo=tz)
    
    delay = (remind_at_dt - now).total_seconds()
    when = max(delay, 1.0)
    
    app.job_queue.run_once(
        reminder_callback,
        when=when,
        data={
            "user_id": user_id,
            "reminder_id": reminder_id,
            "message": message
        },
        name=f"reminder_{reminder_id}"
    )
    logger.info(f"Programado recordatorio {reminder_id} para dentro de {delay:.1f} segundos")

async def load_and_schedule_pending(app: Application) -> None:
    if not app.job_queue:
        return
        
    try:
        tz = zoneinfo.ZoneInfo(TIMEZONE)
    except Exception:
        tz = timezone.utc
        
    pending = await get_pending_reminders()
    logger.info(f"Cargando {len(pending)} recordatorios pendientes de la base de datos...")
    
    for rem in pending:
        try:
            dt = datetime.strptime(rem["remind_at"], "%Y-%m-%d %H:%M:%S")
            schedule_reminder_job(
                app=app,
                reminder_id=rem["id"],
                user_id=rem["user_id"],
                message=rem["message"],
                remind_at_dt=dt
            )
        except Exception as e:
            logger.error(f"No se pudo programar recordatorio {rem['id']}: {e}")

def cancel_reminder_job(reminder_id: int) -> None:
    """Cancela un job programado en el JobQueue si aún no se ha ejecutado."""
    app = get_active_app()
    if not app or not app.job_queue:
        return
    current_jobs = app.job_queue.get_jobs_by_name(f"reminder_{reminder_id}")
    for job in current_jobs:
        job.schedule_removal()
        logger.info(f"Cancelado job en JobQueue para recordatorio {reminder_id}")

