# Idea del proyecto: BiblioLab

## Problema y necesidad

La biblioteca de una escuela maneja libros, alumnos y préstamos. Cuando los registros están en papel o en varias planillas, es fácil perder de vista quién retiró un ejemplar, cuándo debe devolverlo y cuál de las personas que lo solicitaron tiene prioridad. Una simple pantalla para agregar libros no resolvería estas situaciones.

## Solución propuesta

**BiblioLab** es una aplicación web para gestionar el catálogo y el circuito completo de préstamos y reservas. Los alumnos consultan los libros disponibles, solicitan reservas y visualizan préstamos y vencimientos. El bibliotecario administra títulos, alumnos, retiros y devoluciones. El sistema asigna las copias disponibles a una lista de espera por orden de llegada, conserva cada asignación durante un plazo y evita entregar más copias de las existentes.

## Usuarios

- **Alumno:** inicia sesión, consulta el catálogo, reserva, cancela sus reservas, revisa sus movimientos y solicita una renovación.
- **Bibliotecario (administrador):** inicia sesión, administra el catálogo y los usuarios, registra préstamos y devoluciones, controla vencimientos y consulta reservas.

## Recorrido principal

1. Un alumno ingresa, busca un libro y solicita una reserva.
2. Si existe un ejemplar no comprometido, el sistema lo separa por 48 horas. Si no hay, agrega al alumno a una cola de espera.
3. El bibliotecario confirma el retiro y se genera un préstamo con vencimiento a 14 días corridos.
4. El alumno puede renovarlo una sola vez por 7 días, siempre que no esté vencido ni exista alguien esperando el mismo título.
5. Cuando el bibliotecario registra la devolución, el sistema asigna automáticamente el ejemplar al primer alumno en espera.

## Requisitos y límites

- Un alumno puede tener hasta **3 préstamos activos**.
- Los préstamos **vencidos bloquean** nuevos préstamos y reservas.
- No se puede reservar dos veces el mismo título ni reservar uno ya prestado al mismo alumno.
- Cada título posee una cantidad de ejemplares, y un ejemplar asignado a retiro no puede entregarse a otra persona.
- Las reglas se aplican **en el servidor**, no solo en los botones del navegador.
- El proyecto utiliza datos ficticios para demostración. No gestiona multas, pagos, correos ni lectores de códigos de barras.

## Resultado esperado

Una aplicación que permite comprobar desde dos cuentas distintas los casos normales y los casos borde de préstamos, reservas y listas de espera, con código, documentación y pruebas en un mismo repositorio.
