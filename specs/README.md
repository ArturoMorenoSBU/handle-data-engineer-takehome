# specs/

Cada cambio mayor vive en su carpeta: `specs/NNNN-slug/` (ej. `0001-bala-trazadora/`).

| Archivo | Responde | Quién lo escribe |
|---|---|---|
| `INTENT.md` | Qué y por qué, en dos líneas | Humano |
| `SPEC.md` | Qué debe ser cierto al terminar, sin decir cómo | Se saca entrevistando en plan mode; lo aprueba el humano |
| `PLAN.md` | Cómo se hace en este repo, en rebanadas verticales | Lo propone el agente en plan mode; lo corrige y aprueba el humano |

Para empezar uno: `cp -r specs/_template specs/NNNN-slug`.

| Si es... | Va en |
|---|---|
| Una regla del negocio o un resultado esperado | Spec |
| Un archivo, herramienta o configuración de este cambio | Plan |
| Algo cierto para cualquier cambio | `CLAUDE.md` |
| Una decisión con alternativas | ADR, y el plan la cita |
