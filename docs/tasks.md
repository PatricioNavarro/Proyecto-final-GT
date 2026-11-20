# Tasks — BiblioLab

Cada tarea tiene identificador, alcance, rol responsable, dependencia, trazabilidad y definición de terminado. Los ítems de **desarrollo local** están terminados; las acciones en cuentas personales se distinguen al final y no se marcan falsamente como hechas.

- [x] **T01 — Definir la idea y las decisiones.** Agente: analista. RN01–RN20, HU01–HU10. Dep.: ninguna. Criterio: documentos de idea, decisiones, glosario, preguntas y spec coherentes.
- [x] **T02 — Diseñar persistencia y transacciones.** Agente: arquitecto. RN07–RN10, RN16–RN17; HU03, HU05, HU06, HU08. Dep.: T01. Criterio: tablas, índices, transacciones y algoritmo FIFO definidos.
- [x] **T03 — Implementar reglas de negocio.** Agente: backend. RN01–RN20, HU01–HU10. Dep.: T02. Criterio: dominio con permisos, validación, inventario, préstamos, reservas y renovación.
- [x] **T04 — Exponer API y autenticación.** Agente: backend. RN01, RN20; HU01–HU10. Dep.: T03. Criterio: endpoints documentados, sesiones, errores y archivos estáticos servidos.
- [x] **T05 — Implementar frontend para ambos roles.** Agente: frontend. HU01–HU10. Dep.: T04. Criterio: login, catálogo, movimientos, panel, alumnos, préstamos, reservas y formularios.
- [x] **T06 — Escribir y ejecutar pruebas de regresión.** Agente: tester. RN01–RN20; HU01–HU10. Dep.: T03–T05. Criterio: `python -m unittest discover -s tests -v` termina en `OK` (28 pruebas).
- [x] **T07 — Revisar documentación, seguridad y entrega local.** Agente: revisor. RN01–RN20. Dep.: T01–T06. Criterio: AGENTS, reglas de agentes, README, plan, informe, `.gitignore` y ZIP preparados.

## Entrega pública: actividades que requieren la cuenta del alumno

- [ ] **EX01 — Crear repositorio público y subir Git con el historial.** Responsable: alumno. Dependencia: T07. Criterio: enlace GitHub válido, visible sin iniciar sesión.
- [ ] **EX02 — Publicar servicio web.** Responsable: alumno. Dependencia: EX01. Criterio: URL HTTPS abre login y permite probar alumno y administrador con las credenciales configuradas.
- [ ] **EX03 — Completar enlaces públicos en README e informe y enviar el repo al Módulo 5.** Responsable: alumno. Dependencia: EX02. Criterio: URL pública de código y app; comprobación desde navegador externo.
