# Especificación funcional de BiblioLab

Versión 1.0 · 19/11/2026 · Estado de las reglas funcionales: **cerrado, sin pendientes**.

## 1. Objetivo, usuarios y alcance

Digitalizar el catálogo y el circuito de préstamos de una biblioteca escolar con dos roles: **alumno** y **bibliotecario**. Incluye autenticación, consulta, reserva, cola, entrega, devolución, renovación, altas/edición de libros, alta de alumnos y panel administrativo. No incluye pagos, notificaciones por email, escaneo ni asistencia escolar.

## 2. Reglas de negocio

- **RN01. Autenticación y permisos.** Un usuario activo inicia sesión por correo/contraseña. Solo el bibliotecario registra/edita libros, crea alumnos, confirma retiros y devoluciones. La sesión dura 12 horas.
- **RN02. Límite de préstamos.** Un alumno no puede superar **3 préstamos activos**, independientemente de los títulos.
- **RN03. Duración inicial.** Un préstamo vence **14 días corridos** después del retiro, usando fecha de Argentina.
- **RN04. No duplicados.** El mismo alumno no puede recibir dos préstamos activos del mismo título.
- **RN05. Bloqueo por mora.** Con al menos **1 préstamo vencido**, se rechazan nuevos préstamos y nuevas reservas.
- **RN06. Reserva única.** El alumno no puede mantener más de **1 reserva activa** (en espera o lista) del mismo título; tampoco reservarlo si ya lo tiene prestado.
- **RN07. Reserva inmediata.** Si existe una copia sin comprometer, la reserva pasa a **lista**. Si no, queda **en espera**.
- **RN08. Espera FIFO.** Al liberarse un ejemplar se asigna al primer registro en espera, por `(fecha de creación, id)` ascendente.
- **RN09. Plazo de retiro.** Una reserva lista se mantiene **48 horas exactas**; cuando vence pasa a estado vencida y se promueve la siguiente, si la hay.
- **RN10. Prioridad de reservas.** No se permite prestar un ejemplar comprometido a alguien sin reserva lista. Se calcula `disponibles = copias − préstamos activos − reservas listas`.
- **RN11. Confirmación del retiro.** El bibliotecario registra el préstamo y, si había una reserva lista a nombre del alumno, la convierte en cumplida.
- **RN12. Devolución.** El bibliotecario cierra el préstamo con fecha/hora y el sistema reasigna automáticamente las copias liberadas.
- **RN13. Renovación única.** Un alumno puede renovar su préstamo activo **una vez por 7 días corridos**, sumados al vencimiento original.
- **RN14. Restricciones de renovación.** No se renueva si el préstamo está vencido, ya renovado o existe al menos **1 reserva lista o en espera** de otro alumno para ese título.
- **RN15. Cancelación.** Solo el dueño o el bibliotecario pueden cancelar una reserva en estado lista o en espera; después, se reasignan las copias.
- **RN16. Inventario válido.** Cada título debe tener entre **1 y 1000 ejemplares**; una edición no puede bajar de los préstamos activos más reservas listas.
- **RN17. Concurrencia.** Reservas, retiros, devoluciones y reasignaciones ocurren dentro de transacciones de escritura serializadas (`BEGIN IMMEDIATE`); no se crean copias ficticias por carreras simultáneas.
- **RN18. Campos del catálogo.** Cada título debe tener título, autor, categoría, copias e ISBN opcional único. Puede buscarse por título, autor o categoría, sin distinguir mayúsculas.
- **RN19. Alta de alumno.** Solo admin crea alumnos; correo único, nombre válido y contraseña de **8 caracteres como mínimo**.
- **RN20. Datos y seguridad.** Contraseñas PBKDF2-HMAC-SHA256 con salt, sesión mediante cookie HttpOnly y SameSite=Strict, sin contraseñas en el repositorio; en producción se exige `ADMIN_PASSWORD` en variables de entorno.

## 3. Historias de usuario y aceptación

**HU01 — Ingreso al sistema.** Como usuario, quiero ingresar con mi cuenta para ver funciones de mi rol. 
- **Dado** que el usuario está activo y proporciona credenciales válidas, **cuando** inicia sesión, **entonces** se crea una sesión de 12 h y se muestran sus opciones. Cumple RN01, RN20.
- **Dado** que ingresa una contraseña incorrecta, **cuando** inicia sesión, **entonces** recibe un error sin ingresar. Cumple RN01.

**HU02 — Buscar libros.** Como alumno quiero buscar títulos para elegir qué leer.
- **Dado** un catálogo con libros, **cuando** busco parte de un autor, **entonces** veo únicamente las coincidencias y su disponibilidad real. Cumple RN10, RN18.

**HU03 — Reservar ejemplar.** Como alumno quiero reservar un libro para asegurarme la prioridad.
- **Dado** que hay una copia libre, **cuando** reservo, **entonces** queda lista con vencimiento a 48 h. Cumple RN06, RN07, RN09.
- **Dado** que todas están comprometidas, **cuando** reservo, **entonces** quedo en la cola de espera. Cumple RN07, RN08.
- **Dado** que ya reservé el libro o lo tengo prestado, **cuando** lo solicito nuevamente, **entonces** se rechaza. Cumple RN06.

**HU04 — Cancelar reserva.** Como alumno quiero liberar una reserva que ya no necesito.
- **Dado** que la reserva es mía y está activa, **cuando** la cancelo, **entonces** se libera y se asigna la copia al próximo. Cumple RN08, RN15.
- **Dado** que pertenece a otro alumno, **cuando** intento cancelarla, **entonces** se deniega. Cumple RN01, RN15.

**HU05 — Registrar retiro.** Como bibliotecario quiero registrar préstamos sin sobreasignar ejemplares.
- **Dado** un alumno sin moras y con menos de 3 libros, **cuando** retiro una copia libre o reservada a su nombre, **entonces** se genera el préstamo a 14 días. Cumple RN02, RN03, RN10, RN11.
- **Dado** que el último ejemplar ya está reservado para otro alumno, **cuando** intento prestarlo, **entonces** se rechaza. Cumple RN10, RN17.

**HU06 — Registrar devolución.** Como bibliotecario quiero cerrar préstamos y liberar ejemplares.
- **Dado** un préstamo activo y una lista en espera, **cuando** registro devolución, **entonces** el préstamo se cierra y se asigna una reserva lista al primero. Cumple RN08, RN12.

**HU07 — Renovar.** Como alumno quiero extender una sola vez un préstamo.
- **Dado** que está vigente y nadie espera, **cuando** renuevo, **entonces** se agregan 7 días al vencimiento. Cumple RN13.
- **Dado** que hay otra persona esperando, **cuando** renuevo, **entonces** se rechaza sin alterar el vencimiento. Cumple RN14.

**HU08 — Administrar inventario y alumnos.** Como bibliotecario quiero mantener actualizado el catálogo.
- **Dado** que una edición dejaría menos copias que las comprometidas, **cuando** guardo, **entonces** se rechaza. Cumple RN16.
- **Dado** un correo ya registrado, **cuando** creo otro alumno con ese correo, **entonces** se rechaza. Cumple RN19.

**HU09 — Consultar actividad.** Como alumno quiero saber qué libros debo devolver y si una reserva está lista.
- **Dado** que tengo préstamos y reservas, **cuando** abro mis movimientos, **entonces** veo estados, fechas y acciones permitidas. Cumple RN03, RN09, RN13.

**HU10 — Ver estado general.** Como bibliotecario quiero consultar métricas y pendientes.
- **Dado** que hay movimientos, **cuando** abro el panel, **entonces** veo títulos, alumnos, préstamos activos, vencidos y reservas. Cumple RN01, RN05, RN08.

## 4. Casos borde

1. Dos alumnos reservan simultáneamente la **última copia**: solo uno queda listo; el otro, en espera. RN17.
2. Dos bibliotecarios intentan prestar simultáneamente el único ejemplar: solo se confirma uno. RN17.
3. Un alumno busca cancelar la reserva ajena: **404**; no se filtra información adicional. RN15.
4. Un alumno con 3 préstamos intenta un cuarto: **409**. RN02.
5. Una reserva lista supera 48 horas: pasa a vencida; el ejemplar se reasigna al consultar o operar. RN09.
6. Un préstamo vence ayer: no se puede renovar ni crear nuevas reservas. RN05, RN14.
7. Se reduce inventario por debajo de copias comprometidas: rechazo **409**. RN16.
8. Se intenta guardar un ISBN duplicado: rechazo **409**. RN18.
9. Se retorna dos veces el mismo préstamo: el segundo intento falla. RN12.
10. Se intenta acceder a funciones administrativas con cuenta de alumno: **403**. RN01.

## 5. Pendientes de la especificación

**Ninguno dentro del alcance funcional**. La publicación y el enlace GitHub dependen de cuentas externas; ver `preguntas-abiertas.md`.
