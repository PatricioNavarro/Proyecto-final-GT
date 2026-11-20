# Informe final del proyecto — BiblioLab

**Curso:** Generación T · Bootcamp IA-First · Módulos 4 y 5  
**Fecha de preparación:** 19/11/2026  
**Proyecto:** BiblioLab — Gestión de biblioteca escolar  
**Estado:** código/documentación/pruebas locales terminados; despliegue público y GitHub requieren autorización en las cuentas del alumno.

## 1. Introducción y objetivo

Este proyecto propone un sistema web para administrar los préstamos de una biblioteca escolar. Surge de un problema cotidiano: una planilla permite anotar libros y alumnos, pero no impide que se entregue el último ejemplar a dos personas, ni resuelve qué hacer cuando varios alumnos esperan el mismo título. BiblioLab automatiza esas decisiones con reglas de negocio y las hace comprobables.

## 2. Funcionamiento del sistema

Tiene dos tipos de usuarios. Los **alumnos** pueden consultar el catálogo por título, autor o categoría, reservar, cancelar reservas activas, consultar sus préstamos y renovarlos si cumplen las condiciones. El **bibliotecario** puede crear alumnos, agregar y editar libros, registrar retiros y devoluciones, ver reservas y consultar un panel con títulos, usuarios, préstamos activos/vencidos y colas.

Las reglas centrales son: 3 préstamos activos por alumno, plazo de 14 días corridos, una renovación de 7 días, bloqueo de nuevas operaciones si el alumno tiene préstamos vencidos, y retención de ejemplares reservados durante 48 horas. Si una copia no está disponible, la reserva queda esperando; la aplicación respeta el orden de solicitud y reasigna el ejemplar cuando se devuelve o vence la reserva anterior.

## 3. Metodología de trabajo

Se definió primero la necesidad real del negocio y se registraron preguntas/decisiones. A partir de esas respuestas se confeccionó un glosario, una especificación con reglas numeradas y criterios de aceptación, un plan técnico y una lista de tareas. Se establecieron seis perfiles de agentes de IA en `AGENTS.md` y `.cursor/rules/`. La documentación central es `docs/spec.md`. El desarrollo no depende de respuestas improvisadas durante la implementación.

## 4. Plan técnico y por qué se eligió

Frontend: HTML, CSS y JavaScript. Backend: Python con librería estándar. Persistencia: SQLite con claves foráneas, índices e integridad. Una misma aplicación sirve páginas y API; por eso no hace falta configurar CORS. Se eligió una arquitectura simple que se pueda ejecutar localmente sin instalar bibliotecas extras.

La parte más delicada es la **disponibilidad de copias y la cola de espera**, por eso se priorizó antes de las pantallas. Los cambios de préstamos y reservas se realizan con transacciones `BEGIN IMMEDIATE`; así las solicitudes simultáneas no pueden adjudicar la última copia dos veces. La función de reconciliación expira reservas listas y promueve a los primeros de la cola.

**Orden justificado:** definir reglas → diseñar datos y concurrencia → implementar operaciones del servidor → exponer endpoints y autenticación → desarrollar pantallas → probar casos normales y borde → documentar y preparar entrega. Las pantallas dependen de los resultados del servidor, y el servidor depende de decisiones funcionales concretas. El detalle del modelo y los endpoints está en `docs/plan.md`.

## 5. Pruebas realizadas

Comando de verificación real:

```bash
python -m unittest discover -s tests -v
```

**Resultado comprobado el 19/11/2026:** `Ran 28 tests ... OK`. Las pruebas automatizadas están en `tests/test_core.py` y `tests/test_http.py`.

| Grupo de prueba | Ejemplos ejecutados | Resultado |
|---|---|---|
| Autenticación y roles | Login válido/inválido; sesiones; alumno sin permiso de admin | OK |
| Reservas | Primera lista, siguiente en espera; reserva duplicada; cancelación | OK |
| FIFO y vencimiento | Promoción tras cancelación o devolución; 48 horas exactas | OK |
| Límites y fechas | 3 préstamos; 14 días; bloqueo por mora | OK |
| Renovación | +7 días una sola vez; no renovar vencido ni con espera | OK |
| Inventario | Impedir menos copias que compromisos; asignar stock nuevo | OK |
| Concurrencia | Dos reservas simultáneas por última copia; dos retiros simultáneos | OK |
| API real | `/api/health`, frontend, login/cookie, permisos, origen prohibido | OK |

**Aclaración:** son pruebas unitarias/de integración de backend y HTTP local. No se presenta una colección real de Postman ni pruebas de internet porque todavía no se publicó el servicio. El entorno de creación bloqueó la navegación automatizada hacia localhost; por eso no se afirma haber terminado una prueba visual end-to-end en navegador. El frontend se entrega implementado y el instructivo permite probarlo localmente.

## 6. Seguridad

Las contraseñas se guardan con hash PBKDF2-HMAC-SHA256 y sal aleatoria, se manejan cookies HttpOnly y SameSite=Strict, y los permisos se comprueban en backend. La base demo contiene personas ficticias. `.gitignore` excluye `.env` y archivos SQLite. Para publicación se exige configurar `ADMIN_PASSWORD` mediante una variable de entorno, sin incluir claves en el repositorio. No se incluyen datos reales de estudiantes.

## 7. Resultados y casos de uso

El sistema permite recorrer de principio a fin un caso donde Ana reserva el único ejemplar de *Ficciones*, Bruno queda en espera, se registra el retiro de Ana, la renovación se rechaza porque Bruno espera y, tras la devolución, Bruno recibe la primera prioridad. Además se pueden administrar títulos y alumnos, observar el historial y verificar que las decisiones se respetan aunque dos usuarios actúen al mismo tiempo.

## 8. Conclusión

El resultado demuestra que una aplicación de gestión es más que un ABM: necesita definir y controlar las situaciones de negocio. El aprendizaje principal está en pasar de una idea a decisiones claras y comprobables, ordenarlas en reglas e historias, resolver los casos difíciles en el servidor y respaldar su cumplimiento con pruebas automáticas.

## 9. Enlaces de entrega y estado real

- Repositorio GitHub público: **pendiente de crear y subir desde la cuenta del alumno**.
- Aplicación pública HTTPS: **pendiente de desplegar y validar desde la cuenta del alumno**.
- Entrega en Módulo 5: **pendiente de enviar el enlace real al repositorio**.

Los archivos `README.md`, `render.yaml` y el historial Git empaquetado incluyen el procedimiento concreto para completar estas acciones. El almacenamiento gratuito de Render es efímero para SQLite; para uso persistente deberá incorporarse un disco o cambiar la base de datos.
