# Plan técnico — BiblioLab

## 1. Arquitectura y justificación

**Aplicación web monolítica de origen único:** navegador (HTML, CSS, JS) → servidor HTTP Python → servicio de dominio → SQLite. Se eligió este diseño porque funciona con la biblioteca estándar de Python, reduce dependencias y configuración, facilita la corrección docente y evita CORS entre frontend y backend. La base está abstraída detrás de la clase `Library`. Si el proyecto crece, la persistencia puede adaptarse a PostgreSQL con migraciones y pruebas nuevas.

```text
NAVEGADOR (mismo origen HTTP/HTTPS)
   |--> GET /, /styles.css, /app.js (pantallas)
   |--> /api/* (sesión cookie HttpOnly)
             |
        backend/server.py (ruteo, JSON, control de sesión, roles)
             |
        backend/core.py (RN01–RN20 y transacciones)
             |
        SQLite (users, books, loans, reservations, sessions)
```

## 2. Entidades y relaciones

- `users(id, name, email UNIQUE, password_hash, role, active, created_at)` — 1:N con préstamos, reservas y sesiones.
- `books(id, title, author, category, isbn UNIQUE NULLABLE, copies, active, created_at)` — 1:N con préstamos y reservas.
- `loans(id, book_id FK, user_id FK, borrowed_at, due_on, returned_at, renewal_count)` — índice único parcial por (book_id, user_id) cuando está activo.
- `reservations(id, book_id FK, user_id FK, status, created_at, expires_at)` — índice único parcial por (book_id, user_id) cuando está `waiting` o `ready`.
- `sessions(token_hash PK, user_id FK, created_at, expires_at)` — en DB se guarda SHA-256 del token aleatorio, no el token original.

No existe tabla de ejemplares individuales: se administra un contador de copias por título. Esta decisión alcanza para una biblioteca pequeña que no requiere códigos físicos por copia.

## 3. Consistencia, stock y colas

Para cualquier cambio que afecte disponibilidad, el servidor abre `BEGIN IMMEDIATE`; SQLite permite un escritor a la vez. En la misma transacción se ejecuta `reconcile`: (a) vence reservas listas que superaron 48 horas; (b) calcula `copias - préstamos activos - reservas listas`; (c) cambia las primeras reservas `waiting` a `ready` según creación e ID. Solo después se confirma la operación. Esto evita que dos solicitudes asignen la última copia simultáneamente. La reconciliación se hace en consultas relevantes y escrituras, sin servicio cron externo. La disponibilidad mostrada al usuario es informativa: el servidor siempre vuelve a validarla antes de entregar.

## 4. API implementada

| Método | Ruta | Rol | Función |
|---|---|---|---|
| GET | `/api/health` | público | Estado del servidor |
| POST | `/api/auth/login` | público | Iniciar sesión |
| POST | `/api/auth/logout` | autenticado | Cerrar sesión |
| GET | `/api/me` | autenticado | Identidad/rol |
| GET | `/api/books?q=` | autenticado | Catálogo y disponibilidad |
| GET | `/api/my` | autenticado | Préstamos/reservas propios |
| POST | `/api/reservations` | alumno | Reservar |
| DELETE | `/api/reservations/{id}` | dueño/admin | Cancelar reserva |
| POST | `/api/loans/{id}/renew` | alumno dueño | Renovar |
| GET | `/api/admin/dashboard` | admin | Métricas |
| GET | `/api/admin/students` | admin | Alumnos |
| POST | `/api/admin/students` | admin | Alta de alumno |
| POST | `/api/admin/books` | admin | Alta de título |
| PATCH | `/api/admin/books/{id}` | admin | Editar título/copias |
| POST | `/api/admin/checkout` | admin | Confirmar retiro |
| POST | `/api/admin/loans/{id}/return` | admin | Confirmar devolución |
| GET | `/api/admin/loans` | admin | Préstamos e historial |
| GET | `/api/admin/reservations` | admin | Cola y reservas listas |

Datos JSON; errores normalizados como `{"error":"mensaje"}`. El servidor no habilita CORS y rechaza peticiones JSON con origen cruzado.

## 5. Correspondencia RN → módulo

- `RN01, RN19, RN20`: autenticación, autorización, creación de usuarios en `backend/core.py`, cookies/CSP/JSON en `backend/server.py`.
- `RN02–RN06`: `Library.eligible`, `has_overdue`, `reserve`, `checkout`.
- `RN07–RN10, RN17`: `Library.reconcile`, `reserve`, `checkout`, `return_loan`, transacciones con bloqueo de escritura.
- `RN11–RN12`: `Library.checkout` y `return_loan`.
- `RN13–RN14`: `Library.renew`.
- `RN15`: `Library.cancel_reservation`.
- `RN16, RN18`: `Library.save_book`, índices de integridad y `Library.books`.

## 6. Seguridad y limitaciones

Consultas SQL parametrizadas; password PBKDF2-HMAC-SHA256 con salt aleatoria (260.000 iteraciones); sesiones aleatorias de 12 horas hasheadas en base, cookie HttpOnly/SameSite=Strict y Secure en APP_ENV=production; CSP, sin CORS; control de roles del lado servidor; directorio `data/` y `.env` ignorados por Git. Las cuentas de demostración son **ficticias** y de uso académico; si el servicio se publica, debe cambiarse la contraseña admin y desactivarse DEMO_SEED al pasar a uso real. El proyecto **no** incluye recuperación de contraseña, auditoría avanzada ni rate limiting distribuido, por lo tanto no se plantea para producción escolar real con datos personales.

## 7. Despliegue

Se provee `render.yaml` para crear un único servicio web Python en Render que sirve frontend y backend por HTTPS. `ADMIN_PASSWORD` se debe configurar en el panel de Render y nunca en Git. **Advertencia:** el disco de un servicio gratuito es efímero; después de reinicios/redeploy la base SQLite puede recrearse. Para datos persistentes se necesita almacenamiento persistente o migración a PostgreSQL. El repositorio y URL pública solo pueden completarse al conectar las cuentas externas del alumno.

## 8. Estrategia de validación

Se utiliza `unittest` sin dependencias externas. Se prueban flujos básicos, errores, permisos, plazos de 14 días y 48 horas, renovación, stock, cola FIFO, dos solicitudes simultáneas y endpoints HTTP con cookies. Comando: `python -m unittest discover -s tests -v`. En la ejecución de construcción se verificaron **28 tests: OK**. Los resultados reproducibles se documentan en `docs/informe.md`.

## 9. Orden de construcción y dependencias

1. Acordar reglas y casos borde; sin cifras no se pueden definir pruebas correctas.
2. Diseñar esquema y operaciones atómicas (riesgo mayor: último ejemplar/cola).
3. Implementar dominio y verificar tests; todo lo demás depende de esas reglas.
4. Exponer endpoints HTTP y comprobar acceso por rol.
5. Diseñar pantallas y conectar acciones; no duplicar reglas en el navegador.
6. Ejecutar regresión, revisar seguridad, documentar y preparar el despliegue.

Esta secuencia prioriza la regla técnicamente más difícil y con más dependencias: la consistencia de stock y la lista FIFO.
