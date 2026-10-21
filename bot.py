import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    TypeHandler,
    ApplicationHandlerStop,
    ContextTypes,
    filters
)
from telegram.request import HTTPXRequest
from config.settings import TELEGRAM_BOT_TOKEN, validate_config, ALLOWED_USER_IDS
from database.connection import init_db
from database.repository import list_notes, get_pending_reminders, list_events, delete_note, delete_event, delete_reminder
from services.ai_service import process_user_input, user_histories
from services.scheduler import load_and_schedule_pending, set_active_app, cancel_reminder_job

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        return
    user_id = update.effective_user.id
    
    # Si ALLOWED_USER_IDS está configurado y el usuario no está en la lista blanca
    if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
        logger.warning(f"Acceso bloqueado para usuario no autorizado: {user_id} (@{update.effective_user.username})")
        
        if update.callback_query:
            await update.callback_query.answer("⛔ No estás autorizado para usar este bot.", show_alert=True)
            raise ApplicationHandlerStop

        if update.effective_message:
            await update.effective_message.reply_text(
                f"⛔ **Acceso no autorizado**\n\n"
                f"Este asistente es privado. Tu ID de Telegram es:\n`{user_id}`\n\n"
                f"Copiá y pasale este ID al administrador para que te habilite en el sistema.",
                parse_mode="Markdown"
            )
        raise ApplicationHandlerStop

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user and update.effective_message:
        await update.effective_message.reply_text(
            f"🆔 Tu User ID de Telegram es: `{user.id}`",
            parse_mode="Markdown"
        )

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    nombre = user.first_name if user else "estimado"
    
    mensaje = (
        f"👋 ¡Hola {nombre}! Soy tu **Asistente Personal con Inteligencia Artificial**.\n\n"
        "Podés hablarme o enviarme notas de voz de forma completamente natural. "
        "Yo me encargo de interpretar lo que necesitás y organizar tus tareas.\n\n"
        "✨ **¿Qué podés pedirme?**\n"
        "• 📝 *Notas*: 'Anotá que el código de la alarma es 9812'\n"
        "• ⏰ *Recordatorios*: 'Recordame en 45 minutos apagar el horno'\n"
        "• 📅 *Agenda*: 'Agendá reunión con el cliente el jueves a las 3pm'\n"
        "• 🎙️ *Audios*: ¡Mandame un mensaje de voz y te responderé igual!\n\n"
        "Comandos directos útiles:\n"
        "/notas - Ver tus notas guardadas\n"
        "/recordatorios - Ver alarmas pendientes\n"
        "/agenda - Ver tus eventos y citas\n"
        "/limpiar - Reiniciar la memoria de la charla"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def cmd_notas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    notas = await list_notes(user_id)
    if not notas:
        await update.message.reply_text("📋 No tenés ninguna nota guardada todavía.")
        return
    
    lineas = ["📋 *Tus notas guardadas:*\n"]
    for n in notas:
        lineas.append(f"• [ID {n['id']}] *({n['category']})* {n['content']}")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Borrar alguna nota", callback_data="open_del_notes")]])
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown", reply_markup=markup)

async def cmd_recordatorios(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    rems = await get_pending_reminders(user_id)
    if not rems:
        await update.message.reply_text("⏰ No tenés recordatorios pendientes.")
        return
    
    lineas = ["⏰ *Tus recordatorios pendientes:*\n"]
    for r in rems:
        lineas.append(f"• [ID {r['id']}] 🕒 *{r['remind_at']}*\n  📌 {r['message']}")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Borrar algún recordatorio", callback_data="open_del_rems")]])
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown", reply_markup=markup)

async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    eventos = await list_events(user_id)
    if not eventos:
        await update.message.reply_text("📅 No tenés eventos agendados.")
        return
        
    lineas = ["📅 *Tu agenda de eventos:*\n"]
    for e in eventos:
        fin = f" hasta {e['end_time']}" if e.get('end_time') else ""
        lineas.append(f"• [ID {e['id']}] 🗓️ *{e['start_time']}{fin}*\n  📌 {e['title']}")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🗑️ Borrar algún evento", callback_data="open_del_events")]])
    await update.message.reply_text("\n".join(lineas), parse_mode="Markdown", reply_markup=markup)

async def cmd_borrar_nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    notas = await list_notes(user_id)
    if not notas:
        await update.message.reply_text("📋 No tenés notas guardadas para borrar.")
        return
        
    botones = []
    for n in notas:
        resumen = (n['content'][:30] + '...') if len(n['content']) > 30 else n['content']
        botones.append([InlineKeyboardButton(f"🗑️ #{n['id']} - {resumen}", callback_data=f"ask_del_note:{n['id']}")])
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")])
    await update.message.reply_text("Seleccioná la nota que querés borrar:", reply_markup=InlineKeyboardMarkup(botones))

async def cmd_borrar_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    rems = await get_pending_reminders(user_id)
    if not rems:
        await update.message.reply_text("⏰ No tenés recordatorios pendientes para borrar.")
        return
    botones = []
    for r in rems:
        resumen = (r['message'][:30] + '...') if len(r['message']) > 30 else r['message']
        botones.append([InlineKeyboardButton(f"🗑️ #{r['id']} - {resumen}", callback_data=f"ask_del_rem:{r['id']}")])
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")])
    await update.message.reply_text("Seleccioná el recordatorio que querés borrar:", reply_markup=InlineKeyboardMarkup(botones))

async def cmd_borrar_evento(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    eventos = await list_events(user_id)
    if not eventos:
        await update.message.reply_text("📅 No tenés eventos en tu agenda para borrar.")
        return
    botones = []
    for e in eventos:
        botones.append([InlineKeyboardButton(f"🗑️ #{e['id']} - {e['title']}", callback_data=f"ask_del_event:{e['id']}")])
    botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")])
    await update.message.reply_text("Seleccioná el evento que querés borrar:", reply_markup=InlineKeyboardMarkup(botones))


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    logger.info(f"Botón presionado: data='{data}', usuario={user_id}")
    
    try:
        if data == "cancel_action":
            await query.edit_message_text("❌ Operación cancelada.")
            return
            
        if data == "open_del_notes":
            notas = await list_notes(user_id)
            if not notas:
                await query.edit_message_text("📋 No tenés notas para borrar.")
                return
            botones = []
            for n in notas:
                resumen = (n['content'][:30] + '...') if len(n['content']) > 30 else n['content']
                botones.append([InlineKeyboardButton(f"🗑️ #{n['id']} - {resumen}", callback_data=f"ask_del_note:{n['id']}")])
            botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")])
            await query.edit_message_text("Seleccioná la nota que querés borrar:", reply_markup=InlineKeyboardMarkup(botones))
            return

        if data.startswith("ask_del_note:"):
            note_id = int(data.split(":")[1])
            botones = [
                [
                    InlineKeyboardButton("✅ Sí, borrar", callback_data=f"confirm_del_note:{note_id}"),
                    InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")
                ]
            ]
            await query.edit_message_text(
                f"⚠️ ¿Estás seguro de que deseás eliminar la nota **#{note_id}**?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(botones)
            )
            return

        if data.startswith("confirm_del_note:"):
            note_id = int(data.split(":")[1])
            exito = await delete_note(user_id, note_id)
            if exito:
                await query.edit_message_text(f"✅ Nota #{note_id} eliminada correctamente.")
            else:
                await query.edit_message_text(f"⚠️ No se encontró la nota #{note_id}.")
            return

        if data == "open_del_events":
            eventos = await list_events(user_id)
            if not eventos:
                await query.edit_message_text("📅 No tenés eventos para borrar.")
                return
            botones = []
            for e in eventos:
                botones.append([InlineKeyboardButton(f"🗑️ #{e['id']} - {e['title']}", callback_data=f"ask_del_event:{e['id']}")])
            botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")])
            await query.edit_message_text("Seleccioná el evento que querés borrar:", reply_markup=InlineKeyboardMarkup(botones))
            return

        if data.startswith("ask_del_event:"):
            event_id = int(data.split(":")[1])
            botones = [
                [
                    InlineKeyboardButton("✅ Sí, borrar", callback_data=f"confirm_del_event:{event_id}"),
                    InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")
                ]
            ]
            await query.edit_message_text(
                f"⚠️ ¿Estás seguro de que deseás eliminar el evento **#{event_id}** de tu agenda?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(botones)
            )
            return

        if data.startswith("confirm_del_event:"):
            event_id = int(data.split(":")[1])
            exito = await delete_event(user_id, event_id)
            if exito:
                await query.edit_message_text(f"✅ Evento #{event_id} eliminado de tu agenda.")
            else:
                await query.edit_message_text(f"⚠️ No se encontró el evento #{event_id}.")
            return

        if data == "open_del_rems":
            rems = await get_pending_reminders(user_id)
            if not rems:
                await query.edit_message_text("⏰ No tenés recordatorios pendientes para borrar.")
                return
            botones = []
            for r in rems:
                resumen = (r['message'][:30] + '...') if len(r['message']) > 30 else r['message']
                botones.append([InlineKeyboardButton(f"🗑️ #{r['id']} - {resumen}", callback_data=f"ask_del_rem:{r['id']}")])
            botones.append([InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")])
            await query.edit_message_text("Seleccioná el recordatorio que querés borrar:", reply_markup=InlineKeyboardMarkup(botones))
            return

        if data.startswith("ask_del_rem:"):
            rem_id = int(data.split(":")[1])
            botones = [
                [
                    InlineKeyboardButton("✅ Sí, borrar", callback_data=f"confirm_del_rem:{rem_id}"),
                    InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")
                ]
            ]
            await query.edit_message_text(
                f"⚠️ ¿Estás seguro de que deseás eliminar el recordatorio **#{rem_id}**?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(botones)
            )
            return

        if data.startswith("confirm_del_rem:"):
            rem_id = int(data.split(":")[1])
            exito = await delete_reminder(user_id, rem_id)
            if exito:
                cancel_reminder_job(rem_id)
                await query.edit_message_text(f"✅ Recordatorio #{rem_id} eliminado y cancelado.")
            else:
                await query.edit_message_text(f"⚠️ No se encontró el recordatorio #{rem_id}.")
            return
    except Exception as e:
        logger.error(f"Error procesando callback query {data}: {e}", exc_info=True)
        await query.message.reply_text("⚠️ Ocurrió un error al procesar la acción del botón.")

async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in user_histories:
        del user_histories[user_id]
    await update.message.reply_text("🧹 Memoria de la conversación reiniciada.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Usuario"
    text = update.message.text
    
    await update.message.chat.send_action(action=ChatAction.TYPING)
    
    respuesta = await process_user_input(
        user_id=user_id,
        user_name=user_name,
        text_content=text
    )
    
    try:
        await update.message.reply_text(respuesta, parse_mode="Markdown")
    except Exception:
        # Fallback a texto plano si falla el parseo de Markdown
        await update.message.reply_text(respuesta)

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name or "Usuario"
    voice = update.message.voice or update.message.audio
    
    if not voice:
        return
        
    await update.message.chat.send_action(action=ChatAction.RECORD_VOICE)
    
    try:
        audio_data = None
        for intento in range(2):
            try:
                file = await context.bot.get_file(voice.file_id, read_timeout=30.0)
                audio_data = await file.download_as_bytearray(read_timeout=60.0)
                break
            except Exception as dl_err:
                if intento == 1:
                    raise dl_err
                await asyncio.sleep(1)
        
        await update.message.chat.send_action(action=ChatAction.TYPING)
        
        respuesta = await process_user_input(
            user_id=user_id,
            user_name=user_name,
            audio_bytes=bytes(audio_data),
            audio_mime="audio/ogg"
        )
        
        try:
            await update.message.reply_text(respuesta, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(respuesta)
            
    except Exception as e:
        logger.error(f"Error al procesar nota de voz: {e}", exc_info=True)
        await update.message.reply_text("⚠️ No pude procesar tu mensaje de voz. Por favor intentá nuevamente.")

async def post_init(application: Application) -> None:
    set_active_app(application)
    await init_db()
    await load_and_schedule_pending(application)
    logger.info("Base de datos y scheduler inicializados correctamente.")

def main():
    validate_config()
    
    # Timeouts extendidos para descargas de audio y conexiones inestables
    t_request = HTTPXRequest(
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
        pool_timeout=30.0,
        connection_pool_size=16
    )
    
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(t_request)
        .post_init(post_init)
        .build()
    )
    
    # Middleware de autorización global (se ejecuta antes que cualquier otro handler)
    application.add_handler(TypeHandler(Update, auth_middleware), group=-1)

    # Handlers de comandos
    application.add_handler(CommandHandler("id", cmd_id))
    application.add_handler(CommandHandler("mi_id", cmd_id))
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("notas", cmd_notas))
    application.add_handler(CommandHandler("borrar_nota", cmd_borrar_nota))
    application.add_handler(CommandHandler("recordatorios", cmd_recordatorios))
    application.add_handler(CommandHandler("borrar_recordatorio", cmd_borrar_recordatorio))
    application.add_handler(CommandHandler("agenda", cmd_agenda))
    application.add_handler(CommandHandler("borrar_agenda", cmd_borrar_evento))
    application.add_handler(CommandHandler("borrar_evento", cmd_borrar_evento))
    application.add_handler(CommandHandler("limpiar", cmd_limpiar))
    
    # Handlers de botones y callbacks
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Handlers de mensajes
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))
    
    logger.info("Bot Asistente iniciado y escuchando mensajes en Telegram...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
