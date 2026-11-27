# ADR 0003: Cómo se capturan los datos del portal de Brújula

- **Estado:** aceptada
- **Fecha:** 2026-11-27

## Contexto

Brújula solo entrega sus datos en su portal. Cada broker inicia sesión con su cuenta y ve sus pólizas y sus recibos en dos superficies: páginas HTML para personas y respuestas JSON con las mismas rutas (`/api/policies`, `/api/receipts`). Los recibos vienen de dos en dos por página. Si una página que falla se toma por vacía, el broker ve menos recibos abiertos de los que hay, sin aviso. El spec deja abierto qué superficie se captura (sección 7); el ADR 0001 pide decir cuál alimenta a bronze, porque bronze compara versiones por texto, y el ADR 0002 deja a este ADR como la nota de la regla BRU-OBSERVADO. Este ADR usa los términos del spec y de esos dos ADR.

## Decisión

Se captura solo el JSON; el HTML no se captura. La razón está medida: el 2026-11-27 se comparó, en las capturas de los cuatro escenarios con las dos cuentas, cada página HTML con su respuesta JSON, registro por registro y campo por campo (30 registros).

| Qué se comparó | Resultado |
|---|---|
| Campos y valores de pólizas y recibos | Los mismos en las dos superficies, salvo el vencimiento que falta |
| Vencimiento que falta | El JSON distingue la llave ausente (`R-102`) de `null` (`R-101`); el HTML vuelve los dos texto: "Not supplied" y "Not stated (null)" |
| Cuántas filas ofrece la fuente | El JSON lo dice en pólizas y en recibos (`total_rows`); el HTML, solo en recibos |
| Lo que solo trae el HTML | El nombre de la cuenta ("Alder Demo"), que ningún criterio usa |
| Escenario `failure` | La página 2 de recibos de alder responde 503 en las dos superficies |
| Escenario `drift` | El JSON cambia la llave de la lista (`receipts` → `items`); el HTML, solo el título de una columna |

Cómo se captura:

- **Qué se pide.** Por cada cuenta: inicio de sesión, `/api/policies?page=1` y `/api/receipts?page=1`, y después la página que anuncia `next_page`, hasta que sea nula. Las pólizas tienen una sola página (`?page=2` responde 400). No se pide el detalle de un registro (`record`): repite filas de la lista, y en `failure` también falla.
- **Qué queda en landing.** Cada respuesta, también la fallida, tal como llegó, y al lado su contexto: tanda, cuenta de la sesión, tipo, página, hora y código HTTP. La respuesta 503 no dice de qué cuenta ni de qué página es; su contexto sí. La fecha de la foto ya viene dentro de cada respuesta exitosa. No se guardan la contraseña, la cookie ni la respuesta del inicio de sesión; si se rechaza, queda una captura sin bytes con esa causa.
- **Completitud (CA-03).** Por cuenta y tipo, las filas que la fuente dice ofrecer (`total_rows`) contra los registros distintos leídos. Una página que falla, o que no trae la llave de su tipo, no da filas: nunca se lee como una lista vacía. Tras una página fallida no se piden las siguientes, porque no se sabe si existen. En `failure` y en `drift`, alder queda con 2 de 4 recibos, incompleta.
- **Broker.** Sale de la sesión (BRU-PORTAL). Cada respuesta JSON exitosa trae, junto a la lista, un sobre con `broker`, `source_as_of`, `page`, `total_rows` y `next_page`; si su `broker` no es el de la sesión, la respuesta no da filas. Así, una cookie equivocada no pasa los recibos de un broker a otro, aunque los números se repitan entre brokers.
- **No se reintenta.** Un 503 queda como captura fallida. Reintentar es CD-05, un criterio deseable.
- **BRU-OBSERVADO.** Este ADR es su nota. Sus piezas, vistas en las respuestas de los cuatro escenarios: de estructura, la clase JSON, pólizas bajo `policies` y recibos bajo `receipts`, número de póliza `policy_number` y de recibo `receipt_number`, fecha de la foto `source_as_of`, filas ofrecidas `total_rows` y, sin ser obligatoria, que el `broker` del sobre sea el de la sesión; de formato, `amount` con punto decimal y sin separador de miles, `revision` entera y `source_as_of` como instante ISO 8601 con huso; de significado, póliza del recibo `policy_number`, monto `amount`, moneda `currency`, vencimiento `due_date`, estado `status` y revisión `revision`. Con las piezas de BRU-PORTAL y BRU-EJEMPLOS, cada dato obligatorio de Brújula tiene una sola pieza aplicable.

## Alternativas descartadas

- *Solo el HTML.* Habría que traducir de vuelta "Not supplied" y "Not stated (null)", y la página de pólizas no dice cuántas filas tiene, así que no se podría comprobar su completitud. Matiz: en `drift`, un lector que use la clase de cada celda (`field-amount`) seguiría leyendo la página 2.
- *Las dos superficies.* Duplica capturas y lectores para ganar solo el nombre de la cuenta. Mezcladas en bronze, crearían versiones falsas: `R-102` tendría dos textos de vencimiento con la misma revisión.

## Consecuencias

- Capturar solo el JSON no pierde ningún dato de pólizas ni de recibos del lab.
- Una página que falla o cambia de forma se ve como 2 de 4, nunca como cero.
- El total de alder en `failure`, 100.00 USD, no dice por sí solo que faltan recibos: la vista de totales tiene que mostrar al lado si la captura quedó completa.
- El nombre de la cuenta no se guarda; si un día hace falta, se tendrá solo desde entonces.
- Lo que sabe quien captura (las rutas, `page` y `next_page`) vive en su código. La carga lee con las piezas de BRU-OBSERVADO y nunca contacta al portal (CA-04).
- El separador de miles de `amount` no se observó: ningún monto llega a mil. Un `1,500.00` saldría *inválido*, visible.
- La comparación con el HTML vale para este portal, cuyo código se puede leer; en un portal real habría que repetirla.
