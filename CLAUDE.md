# CLAUDE.md

Notas que el agente lee siempre. Entra solo lo que no se deduce leyendo el código; cada línea lleva su porqué. Menos de 200 líneas.

## Contexto
POC local que une dos aseguradoras (Brújula y Aurora) en una base de datos compartida, sin perder lo que significa cada fuente.

## Cómo trabajamos
- Cambio que se describe en una frase: hazlo directo.
- Cambio mayor: sin `SPEC.md` y `PLAN.md` aprobados no hay código. Viven en `specs/NNNN-slug/` junto con `INTENT.md`.
- Ciclo: intent → spec → plan → rebanadas verticales → `make verificar` → revisión con contexto limpio → aprender.
- La primera rebanada es una bala trazadora: lo más delgado posible de punta a punta.
- Una rebanada por sesión, un commit al terminarla. Enséñame el comando y su salida, no un "ya quedó".
- Una decisión con alternativas (como el stack) va en un ADR en `docs/adr/`; el plan la cita.
- `.claude/` crece cuando hace falta, no antes: skill cuando una tarea se repite, subagente cuando hay un rol claro o una tarea ensucia la sesión, hook cuando una regla de aquí se ignora o es un "nunca".

## Comandos: pendiente

## Reglas
- Al repo solo sube lo que explica el resultado: specs, ADRs, código, pruebas y evidencia. Análisis, investigación, brainstorms y borradores van en `_local/`, que git ignora (`.git/info/exclude`). Porqué: el repo se entrega, y cada archivo debe seguir una línea lógica hacia el resultado; lo exploratorio va y viene y no la sigue.
- Todo texto del repo se escribe para quien no estuvo en la conversación: define cada término la primera vez, prefiere la frase simple y conserva el tecnicismo cuando es la palabra exacta. Antes de darlo por terminado, se relee quitando relleno y frases de agente. Porqué: quien lee el repo no tiene nuestro contexto, y lo que no se entiende solo no cuenta como evidencia.
- Specs, ADRs y docs describen un problema de negocio; el contexto del encargo vive en `_local/`. Porqué: el porqué de cada spec debe atacar una causa del negocio.

## Trampas: pendiente
