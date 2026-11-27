# Spec: Base compartida para Brújula y Aurora

## 1. Objetivo y porqué

Reunir en una base de datos local las pólizas y los recibos que dos aseguradoras entregan de forma distinta, para consultarlos juntos sin perder lo que dijo cada una.

Un broker necesita saber qué pólizas y cobros le muestra cada aseguradora y contrastarlo con lo que él dice tener. Conectarse a cada fuente no alcanza: los registros cambian, los identificadores solo valen dentro de su fuente, faltan valores y lo que se aprende de cada aseguradora se pierde en cada integración.

Es una prueba de concepto (POC): dos fuentes y pocos datos, no un servicio en producción.

## 2. Contexto

**Quién lo consume.** Quien consulta los datos reunidos de un broker, sea una persona o un programa, y quien integra una aseguradora nueva.

**Las fuentes.** Todo es ficticio y está en `fuentes/`.

| Fuente | Cómo llega | Moneda |
|---|---|---|
| Brújula | Portal web local, con sesión por broker y respuestas JSON paginadas | USD |
| Aurora | Archivos CSV en dos entregas, `baseline` y `corrected`, descritas en un `manifest.json` | BRL |
| Book | Un CSV con las pólizas que cada broker dice tener | — |

El portal arranca en cuatro escenarios: `baseline` (datos iniciales), `corrected` (un recibo cambia de monto y de revisión), `failure` (una página de recibos responde error 503) y `drift` (una página trae su lista bajo otro nombre).

**Reglas de las fuentes.** Vienen en `fuentes/source-notes/` y en `fuentes/lab/SCENARIOS.md`. Lo que no responden está como supuesto en la sección 5. Las que este spec cita por nombre:

| Regla | Aseguradora | Qué dice | Estado que declara |
|---|---|---|---|
| CONTRACT-17 | Brújula | El monto entra a una suma solo si es un valor monetario válido. `TBD` no es cero | Aceptada |
| AUR-01 | Aurora | El formato de los archivos y el significado de cada columna y de cada estado | Aceptada |
| Ayuda del portal | Brújula | Qué significa `outstanding`; los números se repiten entre brokers; la revisión es del recibo | No declara estado |
| AGENT-22 | Brújula | Propone leer `TBD` como cero. Contradice a CONTRACT-17 | Propuesta, sin verificar |

**Términos**

| Término | Significado |
|---|---|
| Broker | El intermediario que vende pólizas de varias aseguradoras: `alder` o `birch` |
| Recibo | Un cobro de una póliza. Una póliza tiene uno o varios |
| Book | El inventario de pólizas que el broker dice tener |
| Captura | Una respuesta del portal o un archivo, guardado tal como llegó, con cuándo y cómo se obtuvo |
| Foto de la fuente | El estado de la fuente en un momento. La fuente lo fecha con el campo `source_as_of` |
| Revisión | Número que la aseguradora le pone a un recibo y que sube cuando lo cambia |
| Versión | Lo que la fuente declaró de un registro en un momento. La más reciente es la vigente |
| Disposición | El veredicto sobre un valor: si se pudo usar y, si no, por qué |
| Regla | Algo que se sabe de una fuente y que cambia cómo se leen sus datos |
| Derivado | Todo lo que se calcula a partir de las capturas |
| Resultado idéntico | Los mismos registros, versiones, disposiciones y totales. La hora de captura no cuenta |

Los criterios usan el formato EARS: "CUANDO pasa algo, EL SISTEMA DEBE hacer algo". Los montos se escriben con punto decimal (`1500.00 BRL`). En los archivos, la línea 1 es el encabezado.

## 3. Criterios de aceptación (EARS)

Los criterios **CA** son obligatorios. Los **CD** son deseables: se hacen por nivel cuando todos los obligatorios pasan.

### Captura y procedencia
- **CA-01.** CUANDO se obtiene una respuesta de Brújula o un archivo de Aurora, EL SISTEMA DEBE guardarlo tal como llegó, con su contexto: aseguradora; broker, si la captura es de uno solo; qué se pidió; cuándo; la fecha que declara la fuente, si la trae; y si falló y por qué.
- **CA-02.** EL SISTEMA DEBE permitir llegar, desde cualquier versión de una póliza o de un recibo, a todas las capturas donde se observó: respuesta y página en Brújula, archivo y línea en Aurora.
- **CA-03.** CUANDO termina la captura de una fuente, EL SISTEMA DEBE decir si quedó completa. En Brújula compara, por broker, las filas que la fuente dijo ofrecer con las capturadas. En Aurora, completa significa que llegaron todos los archivos que lista el manifest.
- **CA-04.** CUANDO se elimina todo lo derivado y se rehace solo desde las capturas, sin contactar a la fuente, EL SISTEMA DEBE producir un resultado idéntico.

### Identidad y relaciones
- **CA-05.** EL SISTEMA DEBE identificar una póliza por aseguradora, broker y número de póliza, y un recibo por aseguradora, broker y número de recibo. Los cuatro `R-100` del lab son cuatro recibos.
- **CA-06.** EL SISTEMA DEBE relacionar cada recibo con su póliza solo dentro de la misma aseguradora y el mismo broker.
- **CA-07.** EL SISTEMA DEBE conservar los identificadores como texto: la póliza `000123` no se vuelve `123`.

### Valores y su calidad
- **CA-08.** EL SISTEMA DEBE guardar, para el monto, el vencimiento y el estado de cada recibo: el texto tal como llegó, el valor interpretado en un formato común y una disposición.
- **CA-09.** EL SISTEMA DEBE asignar una de estas disposiciones: válido; no suministrado (el campo no viene o viene vacío); nulo explícito (la fuente mandó `null`); no utilizable (una regla aceptada de esa fuente dice que ese texto no es un valor, como `TBD` en Brújula); inválido (no cumple su formato o no existe, como la fecha `31/11/2026`).
- **CA-10.** SI un valor no es válido, ENTONCES EL SISTEMA DEBE dejar vacío el valor interpretado, conservar el texto y no rellenarlo desde otro campo.
- **CA-11.** EL SISTEMA DEBE leer cada fuente con el formato que esa fuente declara, sin adivinarlo. En Aurora, `1.500,00` es mil quinientos y `10/11/2026` es 10 de noviembre.

### Lo compartido y lo propio de cada fuente
- **CA-12.** EL SISTEMA DEBE ofrecer, con los mismos nombres para las dos aseguradoras: de la póliza, su identidad; del recibo, su identidad, su póliza, su monto con moneda, su vencimiento, su estado y su revisión.
- **CA-13.** EL SISTEMA DEBE dejar consultar, por aseguradora, de qué campo de la fuente sale cada nombre común.
- **CA-14.** EL SISTEMA DEBE traducir el estado del recibo a tres valores comunes, con la etiqueta original al lado: `outstanding` y `EM_ABERTO` son *abierto*; `paid` y `LIQUIDADO`, *pagado*; `EM_CONCILIACAO`, una etiqueta sin regla y un estado que no llega, *indeterminado*. *Indeterminado* es un valor, no una disposición.
- **CA-15.** EL SISTEMA DEBE conservar y dejar consultar, con su texto original, lo que solo tiene sentido en su fuente: el estado de la póliza, el ramo (el tipo de seguro) y la referencia de cliente; y de Aurora la vigencia, la prima, el número de cuota y la fecha de pago.

### Recargas, cambios e historial
- **CA-16.** CUANDO se carga otra vez una foto que ya se había cargado, EL SISTEMA DEBE dejar pólizas, recibos y versiones como estaban.
- **CA-17.** CUANDO la misma fila llega repetida en un archivo, EL SISTEMA DEBE contarla como un solo recibo y registrar que llegó más de una vez.
- **CA-18.** CUANDO un recibo llega con una revisión que no se conocía, mayor o menor que la vigente, EL SISTEMA DEBE agregarla como versión y conservar las demás. Una corrección no crea otro recibo.
- **CA-19.** CUANDO un recibo llega con la misma revisión y el mismo contenido en una foto posterior, EL SISTEMA NO DEBE crear una versión.
- **CA-20.** EL SISTEMA DEBE señalar una sola versión vigente por registro: en un recibo, la de mayor revisión; en una póliza, que no trae revisión, la última observada.
- **CA-21.** EL SISTEMA DEBE dar un resultado idéntico sin importar el orden en que se carguen las fotos.
- **CA-22.** EL SISTEMA DEBE mostrar el historial de un recibo, con el origen de cada versión.

### Totales
- **CA-23.** EL SISTEMA DEBE dar el monto abierto conocido por aseguradora, broker y moneda: suma solo recibos vigentes en estado *abierto* con monto válido, y nunca monedas distintas.
- **CA-24.** EL SISTEMA DEBE decir, junto a cada total, cuántos recibos quedaron fuera y por qué: abiertos sin monto utilizable, o con estado indeterminado y su monto.
- **CA-25.** EL SISTEMA NO DEBE sumar la prima de una póliza con los montos de sus recibos.

### Reglas de cada fuente
- **CA-26.** EL SISTEMA DEBE registrar cada regla con: identificador, aseguradora, estado (propuesta, aceptada o rechazada), origen (contrato, documentación de la fuente, observación propia o decisión de este POC), fecha, quién la propuso o la aceptó y la nota que la respalda.
- **CA-27.** EL SISTEMA DEBE aplicar solo las reglas aceptadas.
- **CA-28.** EL SISTEMA NO DEBE elegir entre reglas por su fecha.
- **CA-29.** EL SISTEMA DEBE dar un resultado idéntico con una regla propuesta registrada que sin ella. Con el lab: AGENT-22 se puede consultar y no cambia nada; el monto de `R-103` queda *no utilizable*, y el sistema dice que lo decidió CONTRACT-17.

### Comparación con el book
- **CA-30.** EL SISTEMA DEBE clasificar cada póliza, cruzando por aseguradora, broker y número: en el book y en la fuente; solo en el book; solo en la fuente.
- **CA-31.** CUANDO una póliza está solo en el book, EL SISTEMA DEBE reportarla como "el book la afirma, la fuente no la muestra", y no como cancelada.
- **CA-32.** EL SISTEMA DEBE mostrar la referencia de cliente del book junto a la de la fuente, sin usarla para cruzar ni declarar error si difieren.

### Inspección
- **CA-33.** EL SISTEMA DEBE construirse desde cero con un solo comando: arranca el portal, captura y carga `baseline` y `corrected` de las dos aseguradoras.
- **CA-34.** EL SISTEMA DEBE mostrar con un comando las respuestas preparadas a: cuánto está abierto y qué quedó fuera; el historial de un recibo; qué pólizas están en el book, en la fuente o en los dos; qué reglas tiene cada fuente y en qué estado; qué valores no son válidos; de qué campo sale cada nombre común; y si cada captura quedó completa.
- **CA-35.** EL SISTEMA DEBE permitir que quien lo consulta escriba sus propias consultas sobre la misma base.

### Deseables

| Nivel | Criterio | EL SISTEMA DEBE |
|---|---|---|
| 1 | CD-01 | Decir, para cada valor cuya disposición o traducción decidió una regla, qué regla fue |
| 1 | CD-02 | Listar, por aseguradora, las etiquetas de estado sin regla y cuántos registros trae cada una |
| 1 | CD-03 | Mostrar qué cambió entre dos fotos de una fuente |
| 2 | CD-04 | Responder el estado a un instante dado, con la versión más reciente de cada registro entre las fotos fechadas en ese instante o antes |
| 2 | CD-05 | Reintentar un número limitado de veces un error que la fuente marca como reintentable, antes de registrar la falla |
| 2 | CD-06 | No reintentar un error que no es reintentable |
| 2 | CD-07 | Conservar una respuesta exitosa que no trae la forma esperada, no extraer registros de ella y registrar "forma no reconocida" como causa |
| 3 | CD-08 | Conservar las dos versiones de un recibo que llega con la misma revisión y contenido distinto, marcar la anomalía y dejar vigente la de la foto más reciente |
| 3 | CD-09 | Agregar una versión cuando cambia el contenido de una póliza, y conservar la anterior |

### Valores esperados con los datos del lab

| Aseguradora / broker | Con solo `baseline` | Con `baseline` y `corrected` | Fuera del total, en los dos casos |
|---|---|---|---|
| Brújula / alder | 125.00 USD | 130.00 USD | 1 abierto sin monto utilizable (`R-103`) |
| Brújula / birch | 80.00 USD | 80.00 USD | Ninguno |
| Aurora / alder | 1500.00 BRL | 0.00 BRL | 1 indeterminado por 2400.50 BRL (`R-102`) |
| Aurora / birch | 800.00 BRL | 800.00 BRL | Ninguno |

- **Historial.** `R-102` de alder en Brújula: revisión 1 con 25.00 y revisión 2 con 30.00, vigente. `R-100` de alder en Aurora: revisión 1 `EM_ABERTO`, que llegó dos veces en baseline (líneas 2 y 5), y revisión 2 `LIQUIDADO`, vigente. Los recibos de birch tienen una sola versión.
- **Disposiciones.** En Brújula, de alder: `R-101` tiene vencimiento *nulo explícito*; `R-102`, *no suministrado*; `R-103`, monto *no utilizable*. En Aurora, `R-102` de alder tiene vencimiento *inválido*. Todo lo demás es válido.
- **Relaciones.** `R-102` y `R-103` de alder en Brújula pertenecen a `P-200`, y `R-102` sale de la página 2 de recibos.
- **Completitud.** En Brújula, alder 4 de 4 recibos y 2 de 2 pólizas; birch 1 de 1 y 1 de 1. En Aurora llegan los dos archivos de cada entrega. En `failure` y en `drift`, cada uno en una base vacía, alder queda con 2 de 4 recibos, incompleta.
- **Book.** Seis pólizas en los dos lados; `brujula/alder/P-300` y `aurora/alder/000999` solo en el book; ninguna solo en la fuente. La referencia de cliente coincide en las tres de Brújula y difiere en las tres de Aurora.
- **Estado a un instante (CD-04).** Al `2026-11-03T13:00:00Z`, alder tiene 130.00 USD en Brújula y todavía 1500.00 BRL en Aurora, porque la foto corregida de Aurora es de las 15:00 UTC.

## 4. Fuera de alcance

- Convertir monedas o unir registros de aseguradoras distintas: los datos no traen tipo de cambio ni una tabla que diga cuáles son el mismo.
- Traducir a un nombre común el estado de la póliza o el ramo, y dar disposición a los campos propios de cada fuente.
- Deducir una cancelación porque una fila o una póliza dejó de aparecer.
- Reparar sola una respuesta que cambió de forma.
- Rechazar filas por campos obligatorios faltantes: lo que falta queda marcado con su disposición.
- El flujo de quién aprueba una regla, y declarar que una regla reemplaza a otra. El estado de una regla se escribe a mano.
- Responder "qué sabíamos el día X" por fecha de captura, y los plazos de retención del historial.
- Interfaz gráfica, nube, programación de corridas y una tercera aseguradora.

## 5. Restricciones

- **No se controla la fuente.** Puede cambiar de forma, de etiquetas o de valores sin avisar. Lo que no se reconoce se conserva y se hace visible; no se descarta ni se adivina.
- Corre en local, sin cuentas en la nube y sin llaves. Brújula solo ofrece su portal; Aurora solo entrega archivos. `fuentes/` se usa sin modificar.
- Los montos conservan sus decimales y las sumas son exactas al centavo.
- Ante la duda, se prefiere menos alcance bien verificado.
- Este spec no nombra herramientas. Las decisiones con alternativas están en `docs/adr/`.

**Supuestos.** Las notas de las fuentes no los responden; son decisiones de este POC.

- `outstanding` de Brújula y `EM_ABERTO` de Aurora se tratan como el mismo estado, *abierto*. Brújula dice "no marcado como pagado" y Aurora dice "abierto"; ninguna nota dice que sean equivalentes. La equivalencia no mezcla montos, porque los totales salen por aseguradora y moneda. Si resulta falsa, se cambia la regla y se rehace todo desde las capturas. En una operación real la aceptaría el dueño de la integración, no quien la propone.
- Lo que la aseguradora documenta de su fuente sin declarar estado (la ayuda del portal y su descripción) se registra como regla aceptada, mientras ningún contrato aceptado lo contradiga.
- Una póliza tiene una versión nueva cuando cambia su contenido, porque ninguna fuente le pone revisión. No se sabe cuándo cambió entre dos fotos.
- `source_as_of` es la fecha de la foto de toda la fuente, no la fecha en que cambió un registro: en `corrected` cambia también para birch, que no tuvo cambios.

## 6. Casos raros y errores

| Caso | Dónde aparece | Comportamiento esperado |
|---|---|---|
| Campo ausente y `null` | Brújula, alder `R-102` y `R-101` | Dos disposiciones distintas; ninguna da una fecha |
| Fecha que no existe, `31/11/2026` | Aurora, alder `R-102` | Texto conservado, valor vacío, *inválido*; no se corrige |
| Estado `EM_CONCILIACAO`, o una etiqueta sin regla | Aurora, alder `R-102` | *Indeterminado*; no cuenta como abierto ni como pagado |
| Fila que deja de aparecer | No ocurre en el lab | No es una cancelación; el registro sigue con su última versión |
| La fecha de la foto cambia y el registro no | Brújula corrected, birch | Sin versión nueva |
| Página con error 503 | Brújula `failure`, alder página 2 | Captura fallida con su causa; resultado incompleto, 2 de 4 |
| Lista bajo otro nombre | Brújula `drift`, alder página 2 | Resultado incompleto, 2 de 4, con la causa "forma no reconocida" |
| Husos horarios distintos | Brújula en UTC, Aurora en UTC−3 | Se comparan instantes, no el texto de la fecha |

## 7. Preguntas abiertas

Ninguna. Las que quedaron al aprobar este spec se resolvieron en los ADRs 0001 (capas), 0002 (dónde viven las reglas, y qué va en código, datos, configuración o memoria), 0003 (cómo se captura el portal) y 0004 (herramientas), y en el plan (el lab entra al repo como `fuentes/`).

## 8. Verificación ejecutable

`make verificar` construye todo desde cero con el mismo comando del README (CA-33) y corre una prueba por comprobación, numeradas igual en `tests/test_spec.py`:

1. Los totales y exclusiones con solo `baseline`, y después con `corrected` (CA-23, CA-24, CA-11).
2. Los cuatro `R-100` son cuatro recibos, y `000123` conserva sus ceros (CA-05, CA-07).
3. Cada recibo pertenece a una póliza de su aseguradora y su broker (CA-06).
4. Las disposiciones esperadas, y que todas las demás son válidas (CA-08 a CA-10).
5. Los nombres comunes y la tabla de campos; lo propio de Aurora se consulta con su texto (CA-12, CA-13, CA-15).
6. Cargar dos veces la misma foto no cambia nada (CA-16, CA-19).
7. La fila repetida es un solo recibo con dos apariciones registradas (CA-17).
8. Los historiales esperados, con una sola versión vigente por registro (CA-18, CA-20, CA-22).
9. Cargar `corrected` antes que `baseline` da un resultado idéntico (CA-21).
10. Rehacer desde las capturas da un resultado idéntico (CA-04).
11. La procedencia de cada versión y el contexto de cada captura (CA-01, CA-02).
12. La completitud esperada (CA-03).
13. La prima no entra a ninguna suma (CA-25).
14. CONTRACT-17 aceptada y AGENT-22 propuesta; el resultado es idéntico con AGENT-22 y sin ella, aunque su fecha es posterior (CA-26 a CA-29).
15. El book: seis, dos y cero, con el texto de CA-31 y las referencias lado a lado (CA-30 a CA-32).
16. El comando de respuestas trae sus siete secciones (CA-34).

CA-35 no se automatiza: se muestra con una consulta escrita a mano. Los casos que los datos del lab no traen están en `tests/test_casos_limite.py`.
