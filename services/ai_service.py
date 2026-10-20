import logging
from datetime import datetime
import zoneinfo
from typing import Dict, List, Optional
from google import genai
from google.genai import types
from telegram.ext import Application
from config.settings import GEMINI_API_KEY, TIMEZONE
from services.tools import UserTools

logger = logging.getLogger(__name__)

# Memoria de conversación en memoria (últimos mensajes por usuario)
user_histories: Dict[int, List[types.Content]] = {}
MAX_HISTORY_TURNS = 12

def get_gemini_client() -> genai.Client:
    return genai.Client(api_key=GEMINI_API_KEY)

def build_system_instruction() -> str:
    try:
        tz = zoneinfo.ZoneInfo(TIMEZONE)
    except Exception:
        tz = zoneinfo.ZoneInfo("UTC")
        
    now = datetime.now(tz)
    fecha_hora_str = now.strftime("%Y-%m-%d %H:%M:%S")
    dia_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][now.weekday()]
    
    return f"""Eres un Asistente Personal Ejecutivo inteligente, eficiente y cordial en Telegram.
La fecha y hora actual en la zona horaria del usuario ({TIMEZONE}) es: {dia_semana}, {fecha_hora_str}.

Tus capacidades principales:
1. GESTIÓN DE NOTAS:
   - Para anotar ideas, datos importantes, listas o compras, usa 'guardar_nota'.
   - Para ver qué tiene anotado, usa 'listar_notas'.
   - Para corregir o actualizar el contenido de una nota, usa 'modificar_nota'.
   - Para borrar una nota, usa 'borrar_nota'.

2. RECORDATORIOS Y ALARMAS:
   - Cuando el usuario te pida recordar algo (ej: "recordame mañana a las 10am llamar al contador", "en 15 minutos sacar la pizza"), calcula la fecha y hora exacta en formato 'YYYY-MM-DD HH:MM:SS' basándote en la fecha/hora actual y ejecuta 'crear_recordatorio'.
   - Para consultar recordatorios pendientes, usa 'listar_recordatorios'.
   - Para cancelar o eliminar un recordatorio, usa 'borrar_recordatorio'.

3. AGENDA Y CITAS:
   - Para programar citas o eventos, usa 'agendar_evento'. Si el usuario no indica hora de fin, deja fecha_fin vacío o calcula 1 hora de duración (NO preguntes por la hora de fin).
   - Para consultar compromisos, usa 'consultar_agenda'.
   - Para borrar o cancelar un evento de la agenda, usa 'borrar_evento'.

Pautas de respuesta:
- Siempre sé conciso, profesional y cálido.
- Cuando ejecutes una herramienta, confirma de manera clara y natural al usuario lo que se agendó, guardó o consultó.
- Si el usuario te envía un audio, responde con la misma claridad procesando lo que te dijo.
- Si falta información crítica para agendar (por ejemplo, fecha u hora de inicio no especificada), pregunta educadamente.
"""

async def process_user_input(
    user_id: int,
    user_name: str,
    text_content: Optional[str] = None,
    audio_bytes: Optional[bytes] = None,
    audio_mime: str = "audio/ogg",
    app: Optional[Application] = None
) -> str:
    """Procesa un mensaje de texto o audio del usuario mediante Gemini y ejecuta herramientas."""
    client = get_gemini_client()
    user_tools = UserTools(user_id=user_id)
    
    # Preparar el contenido del turno actual
    parts: List[types.Part] = []
    if audio_bytes:
        parts.append(types.Part.from_bytes(data=audio_bytes, mime_type=audio_mime))
        if text_content:
            parts.append(types.Part.from_text(text=text_content))
    elif text_content:
        parts.append(types.Part.from_text(text=text_content))
    else:
        return "No recibí ningún texto o audio para procesar."

    current_turn = types.Content(role="user", parts=parts)
    
    # Recuperar historial
    history = user_histories.get(user_id, [])
    history.append(current_turn)
    
    # Configuración de generación
    config = types.GenerateContentConfig(
        system_instruction=build_system_instruction(),
        tools=user_tools.get_tool_functions(),
        temperature=0.3
    )

    models_to_try = [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest"
    ]

    last_error = None
    for model_name in models_to_try:
        try:
            chat = client.aio.chats.create(
                model=model_name,
                config=config,
                history=history
            )
            
            response = await chat.send_message(parts)
            reply_text = response.text or "Acción realizada con éxito."
            
            # Actualizar historial a partir de la sesión de chat
            updated_history = chat.get_history()
            if len(updated_history) > MAX_HISTORY_TURNS * 2:
                user_histories[user_id] = updated_history[-MAX_HISTORY_TURNS * 2:]
            else:
                user_histories[user_id] = updated_history
                
            return reply_text
            
        except Exception as e:
            err_msg = str(e)
            logger.warning(f"Error con modelo {model_name}: {err_msg}")
            last_error = e
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                continue
            else:
                break
                
    logger.error(f"Error final al procesar con Gemini para usuario {user_id}: {last_error}", exc_info=True)
    return f"⚠️ Ocurrió un error al procesar tu solicitud: {str(last_error)}"
