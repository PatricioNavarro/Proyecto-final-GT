# Decisiones del negocio

Las preguntas y respuestas se definieron simulando una entrevista con la persona responsable de la biblioteca. Estas decisiones fijan el comportamiento que debe implementar el sistema.

| N.º | Pregunta | Decisión y motivo |
|---|---|---|
| D01 | ¿Quién retira libros? | Solamente alumnos activos; evita préstamos sin responsable. |
| D02 | ¿Quién confirma un retiro? | Solamente el bibliotecario, porque entrega físicamente el ejemplar. |
| D03 | ¿Cuántos libros puede tener un alumno? | 3 préstamos activos, para mantener un reparto razonable. |
| D04 | ¿Cuál es el plazo de devolución? | 14 días corridos desde el retiro; la regla es simple y comprobable. |
| D05 | ¿Hay renovación? | Sí, una vez por 7 días adicionales a la fecha de vencimiento original. |
| D06 | ¿Cuándo se rechaza una renovación? | Si está vencido, ya se renovó o existe otra reserva activa del título. |
| D07 | ¿Qué pasa si un alumno tiene un préstamo vencido? | No puede recibir otro préstamo ni crear una reserva hasta devolverlo. |
| D08 | ¿Qué ocurre al reservar un libro disponible? | Un ejemplar queda marcado como listo para retirar. |
| D09 | ¿Qué sucede cuando no hay disponibilidad? | Se agrega a una lista de espera con orden de llegada. |
| D10 | ¿Cuánto se mantiene un ejemplar reservado? | 48 horas desde que pasa a listo para retirar. |
| D11 | ¿Y si no lo retira? | Su asignación vence y pasa al primer alumno en espera. |
| D12 | ¿Una persona puede reservar dos veces el mismo título? | No; evita que capture varios lugares en la cola. |
| D13 | ¿Se puede reservar un título que ya se tiene prestado? | No; evita duplicaciones y retenciones de ejemplares. |
| D14 | ¿Quién puede cancelar? | El propietario de la reserva o el bibliotecario, si aún está en espera o lista. |
| D15 | ¿Puede prestarse una copia reservada a otro alumno? | No; el ejemplar listo cuenta como comprometido. |
| D16 | ¿Qué pasa si dos usuarios reservan a la vez la última copia? | La operación se serializa en la base de datos. Uno la obtiene y el otro queda en espera. |
| D17 | ¿Puede reducirse la cantidad de ejemplares? | Solo si no queda por debajo de préstamos activos más reservas listas. |
| D18 | ¿Qué días y horarios se usan? | Zona horaria Argentina; 14 días corridos y 48 horas exactas. |
| D19 | ¿Hace falta un aviso por correo? | No. La consulta del estado se realiza dentro del sistema. |
| D20 | ¿Cómo se accede a los datos? | Dos roles, autenticación con sesión y contraseñas hasheadas. |
| D21 | ¿Cómo se muestra la demo? | Un catálogo y usuarios ficticios iniciales, sin datos personales de alumnos reales. |
| D22 | ¿Qué ocurre sin internet? | No existe modo offline: hace falta conexión con el servidor. |

**Decisión técnica relacionada:** SQLite permite operaciones `BEGIN IMMEDIATE` que serializan las escrituras de reservas y préstamos. El backend y el frontend se sirven desde el mismo origen, por lo que no hace falta habilitar solicitudes entre dominios.
