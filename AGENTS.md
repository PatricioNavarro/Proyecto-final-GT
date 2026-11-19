# AGENTS.md — Reglamento común de agentes

## Proyecto y fuentes de verdad

**BiblioLab**, gestión de biblioteca escolar con préstamos, reservas y cola FIFO. Este archivo es el punto de entrada. La **fuente de verdad funcional** es `docs/spec.md`; si hay conflicto, no modificar reglas sin actualizar antes `docs/decisiones.md` y la spec.

Archivos: `docs/idea.md` (problema), `docs/decisiones.md` (preguntas/respuestas), `docs/glosario.md` (vocabulario), `docs/preguntas-abiertas.md` (pendientes), `docs/spec.md` (reglas e historias), `docs/plan.md` (arquitectura), `docs/tasks.md` (tareas), `docs/informe.md` (resultado y pruebas), `backend/core.py` (RN y DB), `backend/server.py` (API), `frontend/` (interfaz), `tests/` (pruebas).

## Stack

Python 3.12+ con librería estándar (`http.server`, `sqlite3`, `unittest`), HTML5, CSS3 y JavaScript moderno. No instalar paquetes para ejecutar la aplicación. DB SQLite. Todo se sirve desde un mismo host/puerto.

## Reglas generales

1. No cambiar números del negocio sin una decisión documentada: 3 préstamos, 14 días, una renovación de 7 días, retiro por 48 horas.
2. No mover validaciones de negocio solo al frontend; la comprobación final debe estar en `backend/core.py`.
3. Escribir con transacciones en cambios de stock, reservas y préstamos (RN17).
4. Usar hora local `America/Argentina/Buenos_Aires` para vencimientos.
5. No guardar contraseñas, tokens, datos reales o `.env` en Git.
6. Escapar los datos mostrados en HTML; la UI nunca debe confiar en textos recibidos desde la API.
7. Si cambia una RN, actualizar su HU, pruebas, decisiones, plan y README según corresponda.
8. No afirmar que el proyecto se publicó o se subió a GitHub si eso todavía no ocurrió.

## Agentes y responsabilidades

- **Analista:** redacta decisiones, glosario, RN/HU y resuelve ambigüedades.
- **Arquitecto:** define modelo, operaciones atómicas, rutas y despliegue.
- **Backend:** implementa APIs, permisos, persistencia y restricciones.
- **Frontend:** construye pantallas y estados de error/espera.
- **Tester:** define casos normales, negativos y de concurrencia; verifica regresiones.
- **Revisor:** controla cumplimiento de spec, seguridad básica, pruebas y criterios de fin.

## Ciclo de cada tarea

1. Analista identifica RN/HU y criterio de terminado.
2. Tester establece al menos un caso comprobable y registra el resultado inicial cuando corresponde.
3. Desarrollador implementa el cambio sin debilitar la prueba.
4. Ejecutar `python -m unittest discover -s tests -v`; corregir hasta que pase.
5. Revisor compara la tarea con la spec y valida que no haya secretos.
6. Actualizar `docs/tasks.md` y hacer un **commit con alcance de una tarea**.

## Condición de terminado

Código accesible, reglas aplicadas en backend, errores tratados, pruebas pasando, documentación consistente y cambios registrados en Git. Publicación e inserción del enlace en el aula son pasos externos posteriores.
