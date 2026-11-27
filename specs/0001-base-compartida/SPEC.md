# Spec: Base compartida para Brújula y Aurora

## 1. Objetivo y porqué

Reunir en una sola base de datos local las pólizas y los recibos que dos aseguradoras entregan de forma distinta, de modo que se puedan consultar juntos sin perder lo que cada una dijo.

Un broker necesita saber qué pólizas y cobros le muestra cada aseguradora y contrastarlo con lo que él dice tener. Conectarse a cada fuente no alcanza: los registros cambian, los identificadores solo valen dentro de su fuente, faltan valores y lo que se aprende de cada aseguradora se pierde en cada integración.

El resultado debe dejar ver cinco cosas: qué registros hay y de dónde vinieron; qué pasa cuando llega lo mismo otra vez o la fuente cambia; qué valores merecen confianza; cómo se conserva lo aprendido de una fuente; y qué se comparte entre aseguradoras y qué es propio de cada una.

Es una prueba de concepto (POC): muestra el enfoque con dos fuentes y pocos datos. No es un servicio en producción.

## 2. Contexto

**Quién lo consume.** Quien consulta los datos reunidos de un broker, sea una persona o un programa, y quien integra una aseguradora nueva. Otro ingeniero debe poder construirlo y consultarlo siguiendo el README.

**Las fuentes.** Todo es ficticio y viene en un lab: un paquete con el portal de Brújula, los archivos de Aurora, el book, el planteamiento del problema y las notas de cada fuente. Dónde vive el lab respecto al repo es una pregunta abierta (sección 7).

| Fuente | Cómo llega | Moneda | Qué trae |
|---|---|---|---|
| Brújula | Portal web local con inicio de sesión por broker y respuestas JSON paginadas | USD | Pólizas y recibos |
| Aurora | Archivos CSV en dos versiones, `baseline` y `corrected`, descritas en un archivo `manifest.json` | BRL | Pólizas y recibos |
| Book | Un CSV de referencia | — | Las pólizas que cada broker dice tener |

El portal de Brújula se puede arrancar en cuatro escenarios:

| Escenario | Qué pasa |
|---|---|
| `baseline` | Datos iniciales |
| `corrected` | Un recibo cambia de monto y de revisión |
| `failure` | La página 2 de recibos del broker alder, y el detalle de sus recibos, responden error 503 |
| `drift` | La página 2 de recibos de alder trae la lista bajo otro nombre de llave en el JSON |

**Reglas de las fuentes.** Vienen en las notas del lab (`source-notes/`) y en la descripción del portal (`lab/SCENARIOS.md`). Este spec se escribió contra esas notas y contra el planteamiento del problema. Lo que no responden está escrito como supuesto en la sección 5. Las que este spec cita por nombre:

| Regla | Aseguradora | Qué dice | Estado que declara |
|---|---|---|---|
| CONTRACT-17 | Brújula | El monto entra a una suma solo si es un valor monetario válido. `TBD` no es cero | Aceptada |
| AUR-01 | Aurora | El formato de los archivos y el significado de cada columna y de cada estado | Aceptada |
| Ayuda del portal | Brújula | Qué significa `outstanding`; los números se repiten entre brokers; la revisión es del recibo | No declara estado |
| AGENT-22 | Brújula | Propone leer `TBD` como cero. Contradice a CONTRACT-17 | Propuesta, sin verificar |

**Términos que usa este spec**

| Término | Significado |
|---|---|
| Aseguradora | La compañía que emite la póliza: Brújula o Aurora |
| Broker | El intermediario que vende pólizas de varias aseguradoras: `alder` o `birch` |
| Póliza | El contrato de seguro |
| Recibo | Un cobro de una póliza. Una póliza tiene uno o varios |
| Cuota | El número de orden de un recibo dentro de su póliza. Solo Aurora lo informa |
| Ramo | El tipo de seguro: auto, patrimonial |
| Book | El inventario de pólizas que el broker dice tener |
| Captura | Una respuesta del portal o un archivo, guardado tal como llegó, con los datos de cuándo y cómo se obtuvo |
| Foto de la fuente | El estado de la fuente en un momento. La fuente lo fecha con el campo `source_as_of` |
| Revisión | Número que la aseguradora le pone a un recibo y que sube cuando lo cambia |
| Versión | Lo que la fuente declaró de un registro en un momento. Un recibo corregido tiene dos versiones |
| Versión vigente | La versión más reciente de un registro según la fuente. Las demás son su historial |
| Disposición | El veredicto sobre un valor: si se pudo usar y, si no, por qué |
| Regla | Algo que se sabe de una fuente y que cambia cómo se leen sus datos. Ejemplo: "`TBD` no es cero" |
| Abierto conocido | La suma de los recibos abiertos cuyo monto se pudo leer |
| Derivado | Todo lo que se calcula a partir de las capturas |
| Cargar | Pasar de capturas a pólizas, recibos y versiones |
| Resultado idéntico | Los mismos registros, versiones, disposiciones y totales. La hora de captura no cuenta |
| EARS | El formato de los criterios de la sección 3: "CUANDO pasa algo, EL SISTEMA DEBE hacer algo" |
| ADR | Documento corto que registra una decisión de diseño y las alternativas que se descartaron |

Los montos se escriben aquí con punto decimal: `1500.00 BRL`. En los archivos, la línea 1 es el encabezado.

## 3. Criterios de aceptación (EARS)

Los criterios **CA** son obligatorios. Los **CD** son deseables: se hacen por orden de nivel cuando todos los obligatorios pasan. Los que no entren quedan como siguiente incremento.

### Captura y procedencia

- **CA-01.** CUANDO se obtiene una respuesta de Brújula o un archivo de Aurora, EL SISTEMA DEBE guardarlo tal como llegó, junto con: la aseguradora; el broker, cuando la captura es de uno solo (en Aurora el broker es un dato de cada fila); qué se pidió (página o archivo); cuándo se capturó; la fecha que declara la fuente, cuando la trae (en Aurora viene en el manifest); y si el intento tuvo éxito o falló y por qué.
- **CA-02.** EL SISTEMA DEBE permitir llegar, desde cualquier versión de una póliza o de un recibo, a todas las capturas donde se observó: la respuesta y su página en Brújula, el archivo y su línea en Aurora.
- **CA-03.** CUANDO termina la captura de una fuente, EL SISTEMA DEBE decir si quedó completa. En Brújula compara, por broker, las filas que la fuente dijo ofrecer con las capturadas. En Aurora, completa significa que llegaron todos los archivos que el manifest lista para esa versión; la fuente no declara cuántas filas trae cada uno.
- **CA-04.** CUANDO se elimina todo lo derivado y se rehace solo desde las capturas guardadas, sin contactar a la fuente, EL SISTEMA DEBE producir un resultado idéntico.

### Identidad y relaciones

- **CA-05.** EL SISTEMA DEBE identificar una póliza por aseguradora, broker y número de póliza, y un recibo por aseguradora, broker y número de recibo. Con los datos del lab, los cuatro recibos `R-100` son cuatro recibos distintos.
- **CA-06.** EL SISTEMA DEBE relacionar cada recibo con su póliza solo dentro de la misma aseguradora y el mismo broker.
- **CA-07.** EL SISTEMA DEBE conservar los identificadores como texto. La póliza `000123` de Aurora no se convierte en `123`.

### Valores y su calidad

- **CA-08.** EL SISTEMA DEBE guardar, para el monto, la fecha de vencimiento y el estado de cada recibo: el texto tal como llegó, el valor interpretado en un formato común y una disposición. Ejemplo: de Aurora llega `10/11/2026`, y el valor interpretado es la fecha 10 de noviembre de 2026.
- **CA-09.** EL SISTEMA DEBE asignar una de estas disposiciones: válido; no suministrado (el campo no viene o viene vacío); nulo explícito (la fuente mandó `null`); no utilizable (una regla aceptada de esa fuente dice que ese texto no es un valor; en Brújula, `TBD`); inválido (el valor no cumple su formato o no existe, como la fecha `31/11/2026`).
- **CA-10.** SI un valor no es válido, ENTONCES EL SISTEMA DEBE dejar vacío el valor interpretado, conservar el texto original y no rellenarlo desde otro campo.
- **CA-11.** EL SISTEMA DEBE leer cada fuente con el formato que esa fuente declara (separador, coma o punto decimal, orden de día y mes), sin adivinarlo. En Aurora, `1.500,00` es mil quinientos.

### Lo compartido y lo propio de cada fuente

- **CA-12.** EL SISTEMA DEBE ofrecer, con los mismos nombres para las dos aseguradoras: de la póliza, su identidad; del recibo, su identidad, su póliza, su monto con moneda, su fecha de vencimiento, su estado y su revisión.
- **CA-13.** EL SISTEMA DEBE dejar consultar, por aseguradora, de qué campo de la fuente sale cada nombre común.
- **CA-14.** EL SISTEMA DEBE traducir el estado del recibo a tres valores comunes y conservar al lado la etiqueta original: `outstanding` y `EM_ABERTO` son *abierto*; `paid` y `LIQUIDADO` son *pagado*; `EM_CONCILIACAO`, cualquier etiqueta sin regla y un estado que no llega son *indeterminado*. *Indeterminado* es un valor común, no una disposición: una etiqueta que llega tiene disposición válida aunque no tenga regla.
- **CA-15.** EL SISTEMA DEBE conservar y dejar consultar, con su texto original y sin traducirlos a un nombre común, los datos que solo tienen sentido en su fuente: el estado de la póliza, el ramo y la referencia de cliente de cada aseguradora, y de Aurora la vigencia, la prima, el número de cuota y la fecha de pago.

### Recargas, cambios e historial

- **CA-16.** CUANDO se carga otra vez una foto de la fuente que ya se había cargado, EL SISTEMA DEBE dejar las pólizas, los recibos y sus versiones igual que estaban.
- **CA-17.** CUANDO la misma fila llega repetida dentro de un archivo, EL SISTEMA DEBE contarla como un solo recibo y dejar registrado que llegó más de una vez.
- **CA-18.** CUANDO un recibo llega con una revisión que no se conocía, mayor o menor que la vigente, EL SISTEMA DEBE agregarla como versión y conservar las demás. El recibo sigue siendo el mismo: una corrección no crea otro recibo.
- **CA-19.** CUANDO un recibo llega con la misma revisión y el mismo contenido en una foto posterior, EL SISTEMA NO DEBE crear una versión nueva.
- **CA-20.** EL SISTEMA DEBE señalar una sola versión vigente por registro: en un recibo, la de mayor revisión; en una póliza, que no trae revisión, la última observada según la fecha de la foto.
- **CA-21.** EL SISTEMA DEBE dar un resultado idéntico sin importar el orden en que se carguen las fotos de una fuente.
- **CA-22.** EL SISTEMA DEBE mostrar el historial de un recibo, con el origen de cada versión.

### Totales

- **CA-23.** EL SISTEMA DEBE dar el monto abierto conocido por aseguradora, broker y moneda, sumando solo recibos vigentes en estado *abierto* con monto válido, y nunca sumando monedas distintas.
- **CA-24.** EL SISTEMA DEBE decir, junto a cada total, cuántos recibos quedaron fuera y por qué: abiertos sin monto utilizable, o con estado indeterminado y su monto.
- **CA-25.** EL SISTEMA NO DEBE sumar la prima de una póliza con los montos de sus recibos, ni repetirla por recibo.

### Reglas de cada fuente

- **CA-26.** EL SISTEMA DEBE registrar cada regla con: un identificador, la aseguradora a la que pertenece, un estado (propuesta, aceptada o rechazada), su origen (contrato, documentación de la fuente, observación propia o decisión de este POC), su fecha, quién la propuso o la aceptó y la nota que la respalda.
- **CA-27.** EL SISTEMA DEBE aplicar solo las reglas aceptadas.
- **CA-28.** EL SISTEMA NO DEBE elegir entre reglas por su fecha.
- **CA-29.** EL SISTEMA DEBE dar un resultado idéntico con una regla propuesta registrada que sin ella. Con los datos del lab: AGENT-22 está registrada como propuesta, se puede consultar y no cambia ningún registro ni total; el monto de `R-103` de alder en Brújula queda *no utilizable*, y el sistema dice que lo decidió CONTRACT-17.

### Comparación con el book

- **CA-30.** EL SISTEMA DEBE clasificar cada póliza, cruzando por aseguradora, broker y número de póliza, en: está en el book y en la fuente; solo en el book; solo en la fuente.
- **CA-31.** CUANDO una póliza está solo en el book, EL SISTEMA DEBE reportarla como "el book la afirma, la fuente no la muestra", y no como cancelada.
- **CA-32.** EL SISTEMA DEBE mostrar la referencia de cliente del book junto a la de la fuente, sin usarla para cruzar y sin declarar error cuando difieren.

### Inspección

- **CA-33.** EL SISTEMA DEBE construirse desde cero con un solo comando documentado en el README: arranca el portal del lab, captura y carga `baseline` y `corrected` de las dos aseguradoras.
- **CA-34.** EL SISTEMA DEBE mostrar con un comando las respuestas ya preparadas a estas preguntas:
  - cuánto está abierto y qué quedó fuera de la suma;
  - cuál es el historial de un recibo;
  - qué pólizas están en el book, en la fuente o en los dos;
  - qué reglas tiene cada fuente y en qué estado;
  - qué valores tienen una disposición distinta de válido;
  - de qué campo de cada fuente sale cada nombre común;
  - si cada captura quedó completa.
- **CA-35.** EL SISTEMA DEBE permitir que quien lo consulta escriba sus propias consultas sobre la misma base.

### Deseables, nivel 1

- **CD-01.** EL SISTEMA DEBE decir, para cada valor cuya disposición o traducción decidió una regla, qué regla fue.
- **CD-02.** EL SISTEMA DEBE listar, por aseguradora, las etiquetas de estado de recibo que no tienen regla y cuántos registros trae cada una.
- **CD-03.** EL SISTEMA DEBE mostrar qué cambió entre dos fotos de una fuente.

### Deseables, nivel 2

- **CD-04.** CUANDO se pide el estado a un instante dado, EL SISTEMA DEBE responder con la versión más reciente de cada registro entre las observadas en fotos de la fuente fechadas en ese instante o antes.
- **CD-05.** SI la fuente responde un error que marca como reintentable, ENTONCES EL SISTEMA DEBE reintentar un número limitado de veces antes de registrar la falla.
- **CD-06.** SI la fuente responde un error que no es reintentable, ENTONCES EL SISTEMA NO DEBE reintentar.
- **CD-07.** SI una respuesta exitosa no trae la forma esperada, ENTONCES EL SISTEMA DEBE conservar la captura, no extraer registros de ella y registrar "forma no reconocida" como causa de la captura incompleta.

### Deseables, nivel 3

- **CD-08.** SI un recibo llega con la misma revisión y contenido distinto, ENTONCES EL SISTEMA DEBE conservar las dos versiones, marcar la anomalía y dejar como vigente la de la foto más reciente.
- **CD-09.** CUANDO cambia el contenido de una póliza, EL SISTEMA DEBE agregar una versión nueva y conservar la anterior en el historial.

### Valores esperados con los datos del lab

**Abierto conocido (CA-23, CA-24)**

| Aseguradora / broker | Con solo `baseline` cargado | Con `baseline` y `corrected` | Fuera del total, en los dos casos |
|---|---|---|---|
| Brújula / alder | 125.00 USD | 130.00 USD | 1 abierto sin monto utilizable (`R-103`) |
| Brújula / birch | 80.00 USD | 80.00 USD | Ninguno |
| Aurora / alder | 1500.00 BRL | 0.00 BRL | 1 indeterminado por 2400.50 BRL (`R-102`) |
| Aurora / birch | 800.00 BRL | 800.00 BRL | Ninguno |

**De qué campo sale cada nombre común (CA-13)**

| Nombre común | Brújula | Aurora |
|---|---|---|
| Broker | La sesión con la que se consultó | `corretora` |
| Número de póliza | `policy_number` | `numero_apolice` |
| Número de recibo | `receipt_number` | `id_cobranca` |
| Monto | `amount` | `valor_parcela` |
| Moneda | `currency` | `moeda` |
| Fecha de vencimiento | `due_date` | `vencimento` |
| Estado del recibo | `status` | `status_cobranca` |
| Revisión | `revision` | `revisao` |

**Lo demás**

- Relaciones (CA-06): `R-102` y `R-103` de alder en Brújula pertenecen a `P-200`.
- Procedencia (CA-02): `R-102` de alder en Brújula sale de la página 2 de recibos. `R-100` de alder en Aurora sale de las líneas 2 y 5 del archivo baseline y de la línea 2 del corrected.
- Completitud (CA-03): en Brújula, alder 4 de 4 recibos y 2 de 2 pólizas; birch 1 de 1 y 1 de 1. En Aurora, llegaron los dos archivos de cada versión.
- Historial de `R-102` de alder en Brújula: revisión 1 con `25.00`, revisión 2 con `30.00`. La vigente es la 2.
- Historial de `R-100` de alder en Aurora: revisión 1 `EM_ABERTO`, que llegó dos veces en el archivo baseline; revisión 2 `LIQUIDADO` con pago el 03/11/2026. La vigente es la 2.
- Recibos de birch: una sola versión en cada aseguradora después de cargar `corrected`.
- Disposiciones: `R-101` de alder en Brújula tiene vencimiento *nulo explícito*; `R-102`, *no suministrado*; `R-103` tiene monto *no utilizable*; `R-102` de alder en Aurora tiene vencimiento *inválido*. Todos los demás montos, vencimientos y estados son válidos.
- Reglas (CA-26): CONTRACT-17 aceptada; AGENT-22 propuesta.
- Book (CA-30 a CA-32): seis pólizas en los dos lados; `brujula/alder/P-300` y `aurora/alder/000999` solo en el book; ninguna solo en la fuente. La referencia de cliente coincide en las tres de Brújula y difiere en las tres de Aurora.
- Qué cambió (CD-03): en Brújula, solo `R-102` de alder: monto 25.00 → 30.00 y revisión 1 → 2. En Aurora, solo `R-100` de alder: estado `EM_ABERTO` → `LIQUIDADO`, pago vacío → 03/11/2026 y revisión 1 → 2; la fila repetida deja de venir.
- Estado a un instante (CD-04): al `2026-11-02T23:59:59Z` salen los totales de baseline; al `2026-11-03T23:59:59Z`, los de corrected; al `2026-11-03T13:00:00Z`, alder tiene 130.00 USD en Brújula y todavía 1500.00 BRL en Aurora, porque la foto corregida de Aurora es de las 15:00 UTC.
- Escenarios `failure` y `drift`, cada uno cargado en una base vacía: alder en Brújula queda con 2 de 4 recibos y la captura marcada incompleta (CA-01, CA-03).

## 4. Fuera de alcance

- Convertir entre monedas. El lab no trae tipo de cambio.
- Unir pólizas, recibos o clientes de aseguradoras distintas. El lab no trae una tabla que diga cuáles son el mismo.
- Traducir a un nombre común el estado de la póliza o el ramo.
- Deducir una cancelación porque una fila o una póliza dejó de aparecer.
- Reparar o adaptar sola una respuesta que cambió de forma.
- Rechazar filas por campos obligatorios faltantes. Hoy ninguna fila se rechaza; lo que falta queda marcado con su disposición.
- Un recibo cuya póliza no se observó. No ocurre en los datos.
- Dar disposición a los campos propios de cada fuente. Se conservan con su texto original.
- El flujo de quién aprueba una regla, y el paso de una etiqueta sin regla a una regla aceptada. En el POC el estado de una regla se escribe a mano.
- Detener la carga cuando dos reglas aceptadas se contradicen, y declarar que una regla reemplaza a otra.
- Responder "qué sabíamos nosotros el día X" por fecha de captura. Se puede rehacer desde las capturas, pero no se ofrece como consulta.
- Plazos de retención y tiempos de recuperación del historial. En el POC todo el historial está disponible de inmediato.
- Interfaz gráfica, nube, programación de corridas y una tercera aseguradora.

## 5. Restricciones

- **No se controla la fuente.** Puede cambiar de forma, de etiquetas o de valores sin avisar. Lo que no se reconoce se conserva y se hace visible; no se descarta ni se adivina.
- Corre en local, sin cuentas en la nube y sin llaves.
- Brújula solo ofrece su portal; Aurora solo entrega archivos.
- El lab se usa sin modificarlo.
- Los montos conservan sus decimales tal como llegaron y las sumas son exactas al centavo.
- Ante la duda, se prefiere menos alcance bien verificado.
- Este spec no nombra herramientas. Las decisiones con alternativas van en ADRs en `docs/adr/`.
- CA-04 es un requisito sobre el resultado: exige poder rehacer lo derivado desde las capturas. No decide cuántas capas hay ni cómo se llaman.

**Supuestos.** Las notas de las fuentes no los responden; son decisiones de este POC.

- `outstanding` de Brújula y `EM_ABERTO` de Aurora se tratan como el mismo estado, *abierto*. Brújula dice "no marcado como pagado" y Aurora dice "abierto"; ninguna nota dice que sean equivalentes. La equivalencia no mezcla montos, porque los totales salen por aseguradora y moneda. Si resulta falsa, se cambia la regla y se rehace todo desde las capturas. En una operación real la aceptaría el dueño de la integración, no quien la propone.
- Lo que la aseguradora o el lab documentan sobre una fuente sin declarar estado (la ayuda del portal de Brújula y la descripción del portal) se registra como regla aceptada con origen "documentación de la fuente", mientras ningún contrato aceptado lo contradiga.
- Una póliza tiene versión nueva cuando cambia su contenido, porque ninguna fuente le pone revisión. Se sabe cuál es la vigente por la fecha de la foto; no se sabe cuándo cambió entre dos fotos.
- `source_as_of` es la fecha de la foto de toda la fuente, no la fecha en que cambió un registro. Se observó en el portal: en `corrected` cambia también para birch, que no tuvo cambios.

## 6. Casos raros y errores

| Caso | Dónde aparece | Comportamiento esperado |
|---|---|---|
| Monto `TBD` | Brújula, alder `R-103` | Texto conservado, valor vacío, disposición *no utilizable*, fuera del total y contado |
| Campo ausente y `null` | Brújula, alder `R-102` y `R-101` | Dos disposiciones distintas; ninguna da una fecha |
| Fecha que no existe, `31/11/2026` | Aurora, alder `R-102` | Texto conservado, valor vacío, disposición *inválido*; no se corrige |
| Estado `EM_CONCILIACAO` | Aurora, alder `R-102` | *Indeterminado*; no cuenta como abierto ni como pagado |
| Etiqueta de estado sin regla | No ocurre en el lab | *Indeterminado*, con su etiqueta original al lado |
| Fila idéntica repetida | Aurora baseline, líneas 2 y 5 | Un recibo; queda registrado que llegó dos veces |
| Fila que deja de aparecer | No ocurre en el lab: en corrected solo desaparece la fila repetida | No es una cancelación; el registro sigue con su última versión |
| Ceros a la izquierda | Aurora, póliza `000123` | Se conserva como texto |
| Mismo número en registros distintos | `R-100` y `P-100` aparecen cuatro veces: en las dos aseguradoras y con los dos brokers | Cuatro registros distintos |
| La fecha de la foto cambia y el registro no | Brújula corrected, birch | Sin versión nueva |
| La prima no es la suma de los recibos | Aurora, alder `P-100`: prima 1500.00, recibos 1650.00 | No se suman |
| Póliza del book que la fuente no muestra | `P-300`, `000999` | "El book la afirma, la fuente no la muestra"; no es una cancelación |
| Página con error 503 | Brújula `failure`, alder página 2 | Captura fallida con su causa; resultado incompleto, 2 de 4. Con CD-05, antes se reintenta |
| Llave del JSON cambiada | Brújula `drift`, alder página 2 | Resultado incompleto, 2 de 4. Con CD-07, la causa dice "forma no reconocida" |
| Sesión no válida o broker pedido por URL | Brújula, errores 401 y 400 | La captura falla con su causa |
| Husos horarios distintos (CD-04) | Brújula en UTC, Aurora en UTC−3 | Se comparan instantes, no el texto de la fecha |
| Instante anterior a la primera foto (CD-04) | — | Responde que no hay datos a esa fecha, no un total en cero |

## 7. Preguntas abiertas

Las resuelven los ADRs o el plan, no este spec.

- **Capas:** cuántas, con qué nombres y qué guarda cada una. Incluye si las versiones se guardan o se recalculan desde las capturas, cómo se marca la vigente y dónde queda vacío un valor que no se pudo interpretar. ADR.
- **Dónde viven las reglas de cada fuente:** en archivos, en la base o en los dos. ADR.
- **Qué va en código, en datos, en configuración o en memoria,** y qué se entiende por memoria: la de la organización (notas, decisiones) o la de los agentes. ADR.
- **Extracción de Brújula:** por las respuestas JSON, por las páginas HTML o por las dos. En este lab el JSON trae todos los campos de pólizas y recibos; el nombre de la cuenta solo sale en el HTML. ADR.
- **Herramientas y almacenamiento.** ADR, después de los anteriores.
- **El lab:** si entra al repo o se descarga aparte, y con qué nombre de carpeta. Hasta que se decida, las notas de las fuentes que cita este spec no están en el repo. Plan.
- **Reintentos:** cuántos y con qué espera. Plan.

## 8. Verificación ejecutable

`make verificar` construye todo desde cero y comprueba:

1. Con solo `baseline` cargado, los totales y exclusiones de la primera columna de la tabla; después de cargar `corrected`, los de la segunda (CA-23, CA-24, y de rebote CA-11).
2. Los cuatro `R-100` son cuatro recibos, y `000123` conserva sus ceros (CA-05, CA-07).
3. `R-102` y `R-103` de alder en Brújula pertenecen a `P-200`, y ningún recibo apunta a una póliza de otra aseguradora o de otro broker (CA-06).
4. Las disposiciones de los valores esperados, y que todas las demás son válidas (CA-08 a CA-10).
5. Los nombres comunes existen para las dos aseguradoras y la tabla de campos coincide con la de este spec (CA-12, CA-13). La vigencia y la prima de Aurora se pueden consultar con su texto original (CA-15).
6. Cargar dos veces la misma foto deja los mismos conteos de registros y de versiones (CA-16).
7. `R-100` de alder en Aurora es un solo recibo con dos apariciones registradas en baseline (CA-17).
8. Los historiales de `R-102` de Brújula y `R-100` de Aurora, con una sola versión vigente cada uno, y birch sin versiones nuevas (CA-18 a CA-20, CA-22).
9. Cargar `corrected` antes que `baseline` da un resultado idéntico (CA-21).
10. Borrar lo derivado y rehacerlo desde las capturas da un resultado idéntico (CA-04).
11. Las procedencias de los valores esperados: página 2 para `R-102`; líneas 2 y 5 para `R-100` (CA-02). Toda captura tiene sus datos de contexto (CA-01).
12. La completitud de los valores esperados: 4 de 4 y 1 de 1 (CA-03).
13. La suma de alder en Aurora no incluye la prima de ninguna póliza (CA-25).
14. CONTRACT-17 está aceptada y AGENT-22 propuesta, cada una con todos sus datos (CA-26). El resultado es idéntico con AGENT-22 registrada y sin ella, comparando registros y disposiciones, no solo totales, aunque AGENT-22 tiene fecha posterior (CA-27 a CA-29).
15. El book: seis, dos y cero; las dos pólizas que solo están en el book salen con el texto de CA-31 y no como canceladas; las referencias de cliente coinciden en Brújula y difieren en Aurora, sin error (CA-30 a CA-32).
16. El comando de respuestas preparadas termina sin error y trae una sección por pregunta (CA-34).

CA-33 lo cumple el propio `make verificar` al construir desde cero. CA-35 no se automatiza: se muestra con una consulta escrita a mano. Para cada criterio deseable que se haga, se agrega la comprobación de su valor esperado.
