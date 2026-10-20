from typing import Optional, List
from datetime import datetime
import zoneinfo
from telegram.ext import Application
from database.repository import (
    create_note, list_notes, delete_note, update_note,
    create_reminder, get_pending_reminders, delete_reminder,
    create_event, list_events, delete_event
)
from services.scheduler import schedule_reminder_job, get_active_app, cancel_reminder_job
from config.settings import TIMEZONE

class UserTools:
    def __init__(self, user_id: int):
        self.user_id = user_id

    def __deepcopy__(self, memo):
        # Evitar problemas de introspección profunda en Google GenAI AFC
        return self

    async def guardar_nota(self, contenido: str, categoria: str = "general") -> str:
        """Guarda una nota o apunte para el usuario.
        
        Args:
            contenido: El texto completo de la nota o apunte que el usuario quiere guardar.
            categoria: Categoría o etiqueta opcional (ej: 'ideas', 'compras', 'trabajo', 'personal').
        """
        note_id = await create_note(self.user_id, contenido, categoria)
        return f"Nota #{note_id} guardada con éxito en la categoría '{categoria}'."

    async def listar_notas(self, categoria: str = "todas") -> str:
        """Obtiene y lista las notas guardadas por el usuario.
        
        Args:
            categoria: Filtro de categoría opcional, o 'todas' para traer todas las notas.
        """
        notas = await list_notes(self.user_id, categoria)
        if not notas:
            return "No tienes notas guardadas en este momento."
        
        resultado = [f"Tienes {len(notas)} nota(s) registrada(s):"]
        for n in notas:
            resultado.append(f"• [ID {n['id']}] ({n['category']}) {n['content']}")
        return "\n".join(resultado)

    async def borrar_nota(self, nota_id: int) -> str:
        """Elimina una nota específica usando su identificador (ID).
        
        Args:
            nota_id: El número ID de la nota a eliminar.
        """
        exito = await delete_note(self.user_id, nota_id)
        if exito:
            return f"Nota #{nota_id} eliminada correctamente."
        return f"No se encontró ninguna nota con ID #{nota_id} para eliminar."

    async def modificar_nota(self, nota_id: int, nuevo_contenido: str) -> str:
        """Modifica o corrige el texto de una nota existente usando su identificador (ID).
        
        Args:
            nota_id: El número ID de la nota a corregir o actualizar.
            nuevo_contenido: El nuevo texto corregido de la nota.
        """
        exito = await update_note(self.user_id, nota_id, nuevo_contenido)
        if exito:
            return f"Nota #{nota_id} actualizada correctamente con el nuevo contenido: '{nuevo_contenido}'."
        return f"No se encontró ninguna nota con ID #{nota_id} para modificar."

    async def crear_recordatorio(self, mensaje: str, fecha_hora: str) -> str:
        """Programa un recordatorio o alarma para avisarle al usuario en una fecha y hora exacta.
        
        Args:
            mensaje: El texto o motivo del recordatorio (ej: 'tomar la pastilla', 'reunión con Juan').
            fecha_hora: La fecha y hora exacta en formato 'YYYY-MM-DD HH:MM:SS' calculada según la zona horaria del usuario.
        """
        try:
            dt = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return f"Error en el formato de fecha '{fecha_hora}'. Debe ser exactamente 'YYYY-MM-DD HH:MM:SS'."
            
        rem_id = await create_reminder(self.user_id, mensaje, fecha_hora)
        
        app = get_active_app()
        if app:
            schedule_reminder_job(app, rem_id, self.user_id, mensaje, dt)
            
        return f"Recordatorio #{rem_id} agendado con éxito para el {fecha_hora}. Te avisaré automáticamente por aquí."

    async def listar_recordatorios(self) -> str:
        """Muestra la lista de recordatorios pendientes que aún no han sonado o vencido."""
        rems = await get_pending_reminders(self.user_id)
        if not rems:
            return "No tienes recordatorios pendientes."
        
        lineas = ["Tus recordatorios pendientes son:"]
        for r in rems:
            lineas.append(f"• [ID {r['id']}] {r['remind_at']} - {r['message']}")
        return "\n".join(lineas)

    async def agendar_evento(self, titulo: str, fecha_inicio: str, fecha_fin: str = "") -> str:
        """Agendar un evento o compromiso en la agenda / calendario.
        
        Args:
            titulo: Nombre del evento o cita (ej: 'Dentista', 'Vuelo a Madrid').
            fecha_inicio: Fecha y hora de inicio en formato 'YYYY-MM-DD HH:MM:SS'.
            fecha_fin: Fecha y hora de finalización en formato 'YYYY-MM-DD HH:MM:SS' (opcional).
        """
        event_id = await create_event(self.user_id, titulo, fecha_inicio, fecha_fin if fecha_fin else None)
        fin_txt = f" hasta {fecha_fin}" if fecha_fin else ""
        return f"Evento '{titulo}' agendado para {fecha_inicio}{fin_txt} (ID #{event_id})."

    async def consultar_agenda(self, fecha: str = "") -> str:
        """Consulta los eventos o citas en la agenda.
        
        Args:
            fecha: Fecha a consultar en formato 'YYYY-MM-DD'. Si se deja vacío, lista los próximos eventos.
        """
        eventos = await list_events(self.user_id, fecha if fecha else None)
        if not eventos:
            if fecha:
                return f"No tienes eventos agendados para la fecha {fecha}."
            return "No tienes eventos registrados en tu agenda."
        
        lineas = [f"Eventos encontrados ({len(eventos)}):"]
        for e in eventos:
            fin = f" a {e['end_time']}" if e.get('end_time') else ""
            lineas.append(f"• [ID {e['id']}] {e['start_time']}{fin} - {e['title']}")
        return "\n".join(lineas)

    async def borrar_evento(self, evento_id: int) -> str:
        """Elimina un evento o cita específica de la agenda usando su identificador (ID).
        
        Args:
            evento_id: El número ID del evento a eliminar.
        """
        exito = await delete_event(self.user_id, evento_id)
        if exito:
            return f"Evento #{evento_id} eliminado correctamente de la agenda."
        return f"No se encontró ningún evento con ID #{evento_id} en tu agenda."

    async def borrar_recordatorio(self, recordatorio_id: int) -> str:
        """Elimina o cancela un recordatorio específico usando su identificador (ID).
        
        Args:
            recordatorio_id: El número ID del recordatorio a cancelar.
        """
        exito = await delete_reminder(self.user_id, recordatorio_id)
        if exito:
            cancel_reminder_job(recordatorio_id)
            return f"Recordatorio #{recordatorio_id} cancelado correctamente."
        return f"No se encontró ningún recordatorio con ID #{recordatorio_id}."

    def get_tool_functions(self) -> List:
        return [
            self.guardar_nota,
            self.listar_notas,
            self.borrar_nota,
            self.modificar_nota,
            self.crear_recordatorio,
            self.listar_recordatorios,
            self.borrar_recordatorio,
            self.agendar_evento,
            self.consultar_agenda,
            self.borrar_evento,
        ]
