# ADR 0002: Dónde vive lo que se sabe de cada fuente

- **Estado:** aceptada
- **Fecha:** 2026-11-27

## Contexto

Quien integra una aseguradora aprende cosas de ella que cambian cómo se leen sus datos: que sus archivos van separados por `;`, que `TBD` en un monto no es cero, que `EM_ABERTO` quiere decir abierto. Si ese conocimiento queda repartido en el código o en la cabeza de alguien, se pierde en la siguiente integración, o se aplica algo que nadie aceptó. Una propuesta sin verificar, como leer `TBD` como cero, podría hacer pasar un total incompleto por completo sin que nadie lo note.

El spec `specs/0001-base-compartida/SPEC.md` define una **regla** como algo que se sabe de una fuente y que cambia cómo se leen sus datos. Pide que cada regla tenga estado, origen, fecha, quién la propuso o la aceptó y una nota de respaldo (CA-26), que solo se apliquen las aceptadas (CA-27), que nunca se elija entre reglas por su fecha (CA-28) y que una regla propuesta no cambie ningún resultado (CA-29). Deja abiertas dos preguntas (sección 7): dónde viven las reglas, en archivos, en la base o en los dos; y qué va en código, en datos, en configuración o en memoria, y qué se entiende por memoria. Este ADR responde las dos.

Usa los términos del spec (sección 2) y del ADR 0001, `docs/adr/0001-capas-de-la-base.md`: landing, bronze, silver, gold, registro, tanda, aparición y carga. Una **fuente** es Brújula, Aurora o el book: el ADR 0001 trata al book como una fuente más. Los términos nuevos se definen donde aparecen.

El ADR 0001 deja tres condiciones:

- Las reglas no salen de las capturas. Si su original vive en la base, esa parte de la base no es derivada y no se borra al rehacer.
- Las vistas de gold que responden "qué reglas tiene cada fuente" y "de qué campo sale cada nombre común" (CA-34) necesitan leer desde la base.
- Lo que se sabe de una fuente lo usan dos capas: bronze usa la estructura para separar registros y campos; silver usa los formatos de valores y las reglas sobre el significado. El spec junta las dos cosas en una sola regla, AUR-01.

Lo que traen las notas de las fuentes:

| Nota | Regla | Fuente | Estado que declara | Qué dice, en corto |
|---|---|---|---|---|
| Contrato de monto | CONTRACT-17 | Brújula | Aceptada | `amount` es texto decimal en USD. `TBD` no es un monto y no es cero |
| Guía de exportación | AUR-01 | Aurora | Aceptada | Formato de los archivos y significado de cada columna y de cada estado |
| Ayuda del portal | (sin identificador) | Brújula | No declara | `outstanding` es "no marcado como pagado"; los números se repiten entre brokers; la revisión es del recibo |
| Descripción del portal | (sin identificador) | Brújula | No declara | Cada sesión ve solo su broker; campo ausente y `null` son distintos; un `outstanding` cuenta en el abierto y un `paid` no |
| Descripción de los ejemplos | (sin identificador) | Brújula y Aurora | No declara | Brújula entrega JSON con montos decimales y fechas ISO; el manifest de Aurora identifica las versiones de la entrega |
| Propuesta de mapeo | AGENT-22 | Brújula | Propuesta, sin verificar | Leer `TBD` como cero. Contradice a CONTRACT-17 |
| `manifest.json` de Aurora | (es una captura, no una nota) | Aurora | No declara | Separador, codificación, formato de fecha, separadores decimal y de miles, moneda y versiones |

El spec ya decide tres cosas que aquí no se reabren. Lo que una fuente documenta sin declarar estado se registra como regla aceptada con origen "documentación de la fuente", mientras ningún contrato aceptado lo contradiga. `outstanding` y `EM_ABERTO` se tratan como *abierto* (supuestos de la sección 5). AGENT-22 se registra como propuesta (CA-29).

## Decisión

### Cuatro lugares para lo que se sabe

Cada cosa que se sabe de una fuente va a uno de cuatro lugares, y se decide con dos preguntas. La primera: ¿puede cambiar una salida de la carga? Una **salida** es lo que escriben bronze y silver; gold se calcula a partir de ahí. La segunda, si puede: ¿es igual para toda fuente, cambia por fuente o cambia con cada captura?

| Lugar | Qué va | Ejemplos | Cómo cambia |
|---|---|---|---|
| **Código** | Lo que vale igual para toda fuente y no debe poder apagarse | Leer solo con las piezas aplicables (apartado siguiente), sin adivinar. Componer la identidad con aseguradora, broker y número (CA-05). Una fecha que no existe queda *inválida* y no se repara. Una página fallida no es una página vacía. Una fila que deja de venir no es una cancelación. Los identificadores son texto | Con un cambio de código y sus pruebas |
| **Configuración** | Lo que cambia por fuente | La lista de reglas y el descriptor de cada fuente | Editando sus archivos en el repositorio |
| **Datos** | Lo que llega con cada captura | Las capturas de landing, incluido el `manifest.json` de cada tanda de Aurora | Con cada captura |
| **Memoria** | Lo que explica y no cambia ninguna salida | Las notas de las fuentes, el spec, los ADRs, las preguntas abiertas y las instrucciones que leen los agentes que ayudan a construir o integrar una fuente | Se escribe y se lee; la carga nunca la lee |

Bronze y silver no están en la tabla porque no son algo que se sabe: se derivan de los datos y de la configuración.

**Qué se entiende por memoria.** Las dos lecturas del spec: la de la organización (notas, decisiones, ADRs) y la de los agentes (las instrucciones y notas que un asistente lee antes de trabajar). Las dos siguen el mismo principio: la memoria informa y no se ejecuta. Si algo que está en memoria debe cambiar una salida, se escribe como regla con estado y con sus piezas. Así una nota cambia de redacción sin mover ningún total, y una propuesta de un agente no llega a la carga por haber quedado escrita en una nota.

### La lista de reglas y el descriptor de cada fuente

El **original** es lo que se edita; lo demás son copias. El original de la configuración son dos clases de archivo del repositorio.

- **La lista de reglas.** Una fila por regla, con los datos de CA-26:
  - identificador;
  - fuente: la aseguradora que pide CA-26, o el book;
  - estado: propuesta, aceptada o rechazada;
  - origen: contrato, documentación de la fuente, observación propia o decisión de este POC;
  - fecha: la de la nota; si la nota no trae fecha, el día en que se escribió la fila;
  - propuesta por, y decidida por (quien la aceptó o la rechazó; vacío mientras está propuesta);
  - la ruta de la nota que la respalda y una frase con lo que dice.

  La lista dice qué se sabe y con qué autoridad; no dice cómo se aplica.
- **El descriptor de cada fuente.** Un conjunto de **piezas**: instrucciones concretas que la carga ejecuta, como "el separador es `;`" o "`EM_ABERTO` es *abierto*". Cada pieza tiene su propio identificador y cita una regla de la lista. Las piezas se agrupan en tres apartados:

| Apartado | Capa que lo usa | Qué piezas lleva |
|---|---|---|
| Estructura | bronze | Cómo se separan registros y campos (en un CSV: codificación, separador y encabezado; en JSON: dónde vienen los registros); lo que la fuente declara de sí misma (fecha de la foto, filas ofrecidas, archivos de la tanda); cómo distingue un campo que no vino de uno nulo explícito; qué campos de la fuente son los de la identidad |
| Formatos de valores | silver; en Aurora, bronze también compara tres de ellos con el manifest | Separador decimal y de miles, formato de fecha, cómo se lee la revisión como número y la fecha de la foto como instante |
| Significado | silver | El resto del diccionario de campos, el mapa de estados del recibo y los textos especiales, como `TBD` |

Los campos de identidad van en estructura porque bronze los necesita para contar registros distintos en la completitud de cada captura (ADR 0001, CA-03). Cómo se compone la identidad es código; la pieza solo dice de dónde sale cada parte: un campo de la fuente o, para el broker de Brújula, la sesión con la que se consultó. El **diccionario de campos** de CA-13 son todas las piezas que dicen de qué campo sale cada nombre común: las de identidad, en estructura, y las demás, en significado.

**Una pieza se aplica solo si su regla está aceptada.** Esas son las **piezas aplicables**. Vale también para la estructura: según el spec, el separador es una regla.

**Datos obligatorios.** El código define qué datos necesita cada clase de fuente. Cada dato de esta tabla es una pieza, y cada pieza de formato nombra el campo al que se aplica:

| Clase | Datos obligatorios, uno por pieza |
|---|---|
| Toda fuente | La clase de la fuente (CSV o JSON); dónde vienen los registros de cada tipo (qué archivo, o qué llave de la respuesta); cada campo de la identidad, por tipo de registro: en las pólizas de una aseguradora, el broker y el número de póliza; en sus recibos, el broker y el número de recibo; en el book, la aseguradora, el broker y el número de póliza |
| CSV (Aurora y el book) | Codificación; separador; encabezado. Uno de cada uno por fuente, para todos sus archivos |
| JSON (Brújula) | Cómo se distingue un campo que no vino de uno nulo |
| Aseguradora (Brújula y Aurora) | La fecha de la foto; lo que la fuente declara para la completitud; cada nombre común de CA-12 que no sea de identidad; el separador decimal del monto; el separador de miles del monto, que puede ser "ninguno"; el formato de fecha del vencimiento; el formato de la revisión; el formato de la fecha de la foto |
| Book | El campo de referencia de cliente |

Cada dato obligatorio necesita exactamente una pieza aplicable. Si no tiene ninguna, o tiene más de una, la carga termina con error antes de escribir nada y dice cuál. Así, un cambio de estado nunca deja un registro sin identidad ni una versión sin orden: o la fuente se lee completa, o la carga no ocurre. Detener la carga cuando un dato obligatorio tiene dos piezas va más allá del spec, que deja fuera detenerla porque dos reglas se contradicen (sección 4). Es deliberado: sin un separador, o con dos, no hay forma de leer la fuente.

**El mapa de estados y los textos especiales no son obligatorios.** Si dos piezas aplicables cubren la misma etiqueta o el mismo texto, digan lo mismo o no, la carga no aplica ninguna: el valor queda como si no hubiera pieza, y una comprobación de `make verificar` falla y nombra las dos. El código traduce a *indeterminado* una etiqueta sin pieza aplicable, con disposición válida y la etiqueta al lado, y también un estado que no llega, con disposición *no suministrado* (CA-09, CA-14). CD-02 lista las etiquetas sin pieza aplicable, incluidas las que tienen una pieza de una regla no aceptada.

**Un texto especial** es una pieza del tipo "este texto, en este campo, tiene esta disposición y este valor interpretado". CONTRACT-17 y AGENT-22 tienen piezas de ese tipo sobre `TBD`. Si cada una se aplica lo decide solo el estado de su regla; si las dos quedaran aplicables, no se aplicaría ninguna (párrafo anterior).

**AUR-01 sigue siendo una sola regla**, como en el spec, con piezas en los tres apartados. La nota declara su estado una vez; por eso AUR-01 tiene una sola fila en la lista. Cada pieza tiene su identificador, así que un valor puede decir qué parte de la guía lo decidió.

**Una regla sin piezas** no cambia ninguna salida. Queda en la lista porque el spec la registra y para que se vea de dónde sale un comportamiento del código o un supuesto.

Cómo quedan con los datos del lab, suponiendo que Brújula se captura por sus respuestas JSON, como el ejemplo del ADR 0001; lo decide el ADR de extracción:

| Regla | Fuente | Estado | Origen | Nota | Piezas que respalda |
|---|---|---|---|---|---|
| CONTRACT-17 | Brújula | aceptada | contrato | `source-notes/accepted-contract.md` | Significado: `TBD` en `amount` es *no utilizable*, sin valor interpretado |
| BRU-AYUDA | Brújula | aceptada | documentación de la fuente | `source-notes/carrier-help.md` | Ninguna. Documenta que el número vale dentro del broker y que la revisión es del recibo, que aplica el código, y el supuesto de BRU-ESTADOS |
| BRU-PORTAL | Brújula | aceptada | documentación de la fuente | `lab/SCENARIOS.md`, apartado *Portal semantics* | Estructura: el broker de las pólizas y el de los recibos sale de la sesión; un campo que no vino y uno `null` son distintos. Significado: `paid` es *pagado* |
| BRU-EJEMPLOS | Brújula | aceptada | documentación de la fuente | `fixtures/README.md` | Formatos: el vencimiento es una fecha ISO, año-mes-día |
| BRU-OBSERVADO | Brújula | aceptada | observación propia | El ADR de extracción de Brújula | Estructura: la clase JSON, dónde vienen los registros, lo que declara cada respuesta (`source_as_of`, `total_rows`), los campos de número de póliza y de recibo. Formatos: punto decimal y sin separador de miles en `amount`, revisión entera, `source_as_of` como instante. Significado: el resto del diccionario |
| BRU-ESTADOS | Brújula | aceptada | decisión de este POC | `specs/0001-base-compartida/SPEC.md`, supuestos de la sección 5 | Significado: `outstanding` es *abierto* |
| AUR-01 | Aurora | aceptada | documentación de la fuente | `source-notes/aurora-contract.md` | Estructura: la clase CSV, UTF-8, separador `;`; en pólizas, `corretora` y `numero_apolice`; en recibos, `id_cobranca`. Formatos: coma decimal y punto de miles en `valor_parcela`, día/mes/año en `vencimento`. Significado: el resto del diccionario; `EM_ABERTO` es *abierto*, `LIQUIDADO` es *pagado*, `EM_CONCILIACAO` es *indeterminado* |
| AUR-OBSERVADO | Aurora | aceptada | observación propia | `docs/adr/0002-reglas-de-cada-fuente.md` | Estructura: encabezado en la primera línea; qué archivo trae pólizas y cuál recibos; del manifest, la fecha de la foto (`source_as_of` de cada versión) y los archivos de la tanda (`files`); en recibos, `corretora`. Formatos: revisión entera; `source_as_of` como instante con su huso. Significado: en recibos, `numero_apolice` como su póliza. La guía describe `corretora` y `numero_apolice` solo en la exportación de pólizas |
| BOOK-01 | book | aceptada | observación propia | `docs/adr/0002-reglas-de-cada-fuente.md` | Estructura: la clase CSV, un solo archivo, UTF-8, separador `,`, encabezado en la primera línea, los campos de identidad (`carrier`, `broker`, `policy_number`). Significado: `customer_reference` |
| AGENT-22 | Brújula | propuesta | observación propia | `source-notes/mapping-proposal.md` | Significado: `TBD` en `amount` es *válido*, con valor 0 |

Cómo se leen algunas filas:

- **Rutas.** Las que empiezan por `source-notes/`, `lab/` o `fixtures/` son del lab; las demás, del repositorio. La nota de BRU-OBSERVADO tendrá la ruta del ADR de extracción.
- **Una celda puede nombrar varias piezas.** "Lo que declara cada respuesta (`source_as_of`, `total_rows`)" son dos piezas, una por dato obligatorio; lo mismo con el broker de pólizas y de recibos. "El resto del diccionario" son los nombres comunes que la fila no asigna a otra regla.
- **`EM_ABERTO` y `outstanding` tienen respaldos distintos.** AUR-01 dice que `EM_ABERTO` significa abierto. Brújula dice que `outstanding` es "no marcado como pagado" y que cuenta en el abierto conocido. Que las dos etiquetas sean el mismo *abierto* compartido es un supuesto del spec, y por eso va en una decisión de este POC.
- **Decidida por.** En CONTRACT-17 y AUR-01 la decidió el dueño que nombra la nota. En las de documentación sin estado declarado, en las de observación propia y en las de este POC, quien escribió la fila, que comprueba a mano que ningún contrato aceptado las contradiga.
- **AGENT-22 tiene origen "observación propia"** en el sentido de que sale de nosotros y no de la fuente: es una nota de exploración del asistente que integra fuentes, y la propia nota dice que no verificó nada. Ninguno de los cuatro orígenes de CA-26 es "propuesta de un agente"; quién la propuso queda en "propuesta por".
- **Las tres reglas de observación aceptadas** cubren lo que ninguna nota declara. Brújula dice "texto decimal" sin decir el separador; el punto decimal es una observación aceptada como regla, que no se vuelve a adivinar en cada carga (CA-11).

### El original vive en archivos y silver tiene una copia

- **El original son los archivos del repositorio.** Se cambian como se cambia el código: editando y guardando el cambio en el historial del repositorio, que registra quién y cuándo.
- **Cada carga copia la lista y los descriptores a tablas de silver**, que se reemplazan enteras junto con el resto de silver. Nadie las edita: lo que se edite ahí se pierde en la carga siguiente. Así, la copia de las reglas es siempre la misma con que se calculó silver.
- **Orden de una carga.** Lee la lista y los descriptores, resuelve las piezas aplicables y comprueba los datos obligatorios y la guarda del punto siguiente. Después agrega a bronze lo que falta y recalcula silver, copia incluida. Si la carga termina con error, no cambia nada.
- **La base es derivada entera.** Rehacer usa las capturas de landing y lo que se sabe de cada fuente, que no viene en ellas (ADR 0001). CA-04 se comprueba borrando la base completa.
- **Un cambio en lo que lee bronze obliga a rehacer la base.** Bronze solo agrega apariciones (ADR 0001), así que las viejas quedarían separadas con las piezas anteriores. La carga compara, fuente por fuente, el campo y el valor de cada pieza aplicable que lee bronze con los de la copia de la carga anterior: las de estructura y, en Aurora, las tres de formato que compara con el manifest. No compara identificadores. Si difieren, porque cambió una pieza o el estado de su regla, la carga termina con error y pide rehacer la base: borrarla y cargar. Si una fuente no tiene filas en bronze, no hay nada con qué comparar. Si las tiene y la copia anterior no trae sus piezas, la carga también pide rehacer.
- **Qué regla puede cambiar las versiones.** Una pieza que solo usa silver no puede crear ni borrar una versión, porque las versiones se distinguen por el texto de bronze (ADR 0001). Una pieza que lee bronze sí puede, porque cambia qué texto llega a bronze o si llega: las de estructura y, en Aurora, las tres de formato que bronze compara con el manifest. El ADR 0001 ya lo prevé en "Lo que cuesta". Por eso esas piezas solo actúan al rehacer la base.

### Solo se aplica lo aceptado

- **El filtro.** Antes de leer capturas, un paso de código resuelve las piezas aplicables. Tiene que ser antes porque bronze necesita la estructura para abrir los archivos. Bronze y silver calculan solo con ese conjunto, que además queda escrito en su propia tabla de silver, junto con el resto de silver. La copia completa de reglas y piezas, propuestas y rechazadas incluidas, solo la lee gold (CA-29 pide que AGENT-22 se pueda consultar).
- **La fecha no decide.** Ningún cálculo de bronze o de silver usa la fecha de una regla; la fecha se copia para mostrarla en gold (CA-28).
- **Qué pieza decidió.** En el monto, el vencimiento y el estado de cada recibo, silver guarda los identificadores de las piezas que decidieron su disposición o su valor interpretado y, a través de ellas, los de sus reglas:
  - un texto especial: la pieza del texto; por ejemplo, `R-103` de alder en Brújula es *no utilizable* por la pieza de CONTRACT-17 (CA-29);
  - un valor válido o inválido: las piezas de formato de ese campo (en un monto, la del separador decimal y la del de miles);
  - un campo que no vino o vino nulo: la pieza de estructura que distingue los dos casos;
  - un estado: la pieza del mapa.

  Queda vacío cuando lo decidió el código: un campo vacío en un CSV y un estado sin pieza aplicable. Así se cumple CD-01.
- **Lo que prueba AGENT-22.** La prueba de CA-29 muestra que una pieza propuesta no se aplica. No muestra que se aplicaría si se aceptara: eso pide una prueba que, en una lista de reglas de prueba, la acepte y rechace CONTRACT-17, y compruebe el cambio (un control positivo). Queda fuera de este alcance.

### El formato de Aurora: dos declaraciones que deben coincidir

- Bronze lee con la estructura que declara la fuente (ADR 0001). Aurora la declara dos veces: en su guía AUR-01, de donde salen las piezas del descriptor, y en el manifest de cada tanda. Bronze solo lee una tanda cuando las dos coinciden; entonces lo que usa es a la vez la pieza de AUR-01 y lo que declara el manifest.
- Compara cinco valores, las llaves `delimiter` y `encoding` (estructura) y `date_format`, `decimal_separator` y `thousands_separator` (formato), con las piezas de separador, codificación, formato del vencimiento, separador decimal y separador de miles. Cada pieza guarda el valor escrito como lo escribe el manifest (por ejemplo, `DD/MM/YYYY`), y la comparación es por texto. Una llave que falta, o un manifest que no se puede leer, cuenta como diferencia.
- Si algo difiere, todas las capturas de la tanda, manifest incluido, quedan como "forma no reconocida" (CD-07), con la diferencia escrita, y no dan filas de registros.
- Brújula no declara su formato en sus respuestas; no hay nada que comparar.

## Alternativas descartadas

**Dónde vive el original de las reglas**

- *La base como original, en tablas que no se borran al rehacer.* Las reglas se editan sin tocar el repositorio, como en un catálogo de datos. Se descartó porque:
  - construir desde cero con un comando (CA-33) obliga de todos modos a un archivo con las reglas iniciales, que sería un segundo original;
  - CA-04 dejaría de comprobarse borrando la base entera;
  - entre un cambio de estado y la carga siguiente, la vista de reglas diría "aceptada" de una regla con la que silver no se calculó;
  - no perder el estado anterior pide una tabla de historial y modificar filas, algo que el ADR 0001 no pide.
- *Archivos como original, leídos desde una vista sin copiarlos.* Ahorra la copia. Depende de que el motor de la base pueda leer un archivo dentro de una vista, y entre un cambio y la carga siguiente la vista mostraría reglas distintas de las que usó silver.
- *Un catálogo de datos con flujo de aprobación.* Un **catálogo de datos** es una aplicación donde se registran los conjuntos de datos, su significado y sus dueños; en algunos, lo que propone un agente entra como borrador y solo una persona lo acepta. Sería el paso siguiente si varias personas proponen y aceptan reglas. Se descartó por tamaño: pide de 6 a 8 GB de memoria y varios servicios (base de datos, motor de búsqueda, orquestador), y el spec deja fuera el flujo de aprobación (sección 4).
- *Guardar en cada carga una huella del conjunto de reglas aplicables*, un resumen corto que cambia si cambia el contenido, para saber después con qué reglas se calculó un total. Se descartó porque silver se recalcula completa: la base solo tiene un conjunto de reglas a la vez, y el historial está en el repositorio.

**Qué cuenta como regla y cómo se parte AUR-01**

- *La estructura como configuración sin estado*, revisada como código. Bronze nunca dependería del estado de una regla. Se descartó porque contradice la definición de regla del spec, y porque obligaría a partir AUR-01, que incluye el formato de los archivos.
- *Partir AUR-01 en varias filas de la lista*, una por apartado, cada una con su estado. Permitiría aceptar una parte de la guía y no otra. Se descartó porque la nota declara su estado una sola vez: quedarían tres filas con el mismo estado, origen, fecha y nota. Qué parte decidió un valor ya lo dice el identificador de la pieza.

**En qué formato se escriben la lista y los descriptores**

- *Un estándar.* Frictionless Table Dialect y Table Schema, o CSVW, ya nombran el separador, la coma decimal, el formato de fecha y los textos que significan "falta". LinkML tiene un campo de estado por elemento. Se descartó porque ninguno aplica el estado en la transformación: el filtro de lo aceptado sería código propio igual. Sus nombres se pueden usar dentro del formato propio.

**De dónde sale el formato de Aurora**

- *Solo del descriptor, sin mirar el manifest.* Lo más simple. Se descartó porque un cambio de formato se leería mal sin aviso: si una entrega pasa a punto decimal, `1.500`, que sería uno y medio, se leería como mil quinientos.
- *Solo del manifest de cada tanda*, con una regla aceptada que diga "el formato es el que declara cada manifest". Cada tanda se leería con su propio formato. Se descartó porque, si la guía y el manifest dijeran cosas distintas, lo resolvería en silencio a favor del manifest.

**Qué se rehace cuando cambia lo que lee bronze**

- *Rehacer solo la parte de bronze de la fuente afectada*, que ya tiene sus propias tablas (ADR 0001). Ahorra releer las demás fuentes. Se descartó por tamaño: borrar la base y cargar ya existe y es lo que comprueba CA-04; rehacer por partes pide saber con qué piezas se separó cada captura.

**Dónde viven el diccionario de campos y el mapa de estados**

- *En el código de silver*, una expresión por etiqueta. Se descartó porque lo que está en el código siempre se ejecuta: un mapeo propuesto no podría quedar sin aplicar (CA-27). Además, una fuente nueva obligaría a tocar el código.
- *En archivos tabulares aparte*, por ejemplo en CSV. Con la copia en silver, el diccionario y el mapa ya se consultan como tablas; separarlos dejaría lo que se sabe de una fuente en tres clases de archivo.

**Cómo se garantiza que solo entra lo aceptado**

- *Separación por ubicación*: lo propuesto vive solo en la lista, sin pieza, y aceptar una regla es escribir su pieza en el descriptor. Se descartó porque deja dos marcas de lo mismo, la ubicación y el estado, que pueden contradecirse. Además, AGENT-22 sin pieza haría que CA-29 se cumpla sin que el filtro se ejerza.
- *Precedencia por autoridad*: el contrato antes que la documentación, y esta antes que una propuesta. Decidiría sola conflictos que conviene ver, y CA-27 ya deja fuera todo lo que no está aceptado.

**Memoria**

- *Que la carga lea las notas*, con el estado en un encabezado de cada nota. Una nota tendría que seguir un formato estricto, y un cambio de redacción podría mover un resultado.

## Consecuencias

**Simulación a mano con los datos del lab**

1. **Borrar la base y rehacerla (CA-04).** La carga lee las diez reglas y los tres descriptores (Brújula, Aurora y el book), encuentra exactamente una pieza aplicable para cada dato obligatorio, agrega todas las tandas a bronze y recalcula silver. Las reglas salen de los mismos archivos, así que el resultado es idéntico.
2. **Registrar y quitar AGENT-22 (CA-29).** Se comparan dos bases: una con AGENT-22 y su pieza, otra sin las dos.
   - La pieza no es aplicable, y `TBD` no es un dato obligatorio, así que la carga sigue. Bronze es igual en las dos bases.
   - En silver, en las dos, el monto de `R-103` tiene texto `TBD`, valor vacío, disposición *no utilizable* y la pieza de CONTRACT-17. El abierto conocido de Brújula / alder es 125.00 USD con solo baseline y 130.00 USD con corrected, con un abierto sin monto utilizable.
   - Solo cambia la copia completa de reglas, que gold muestra. No forma parte del "resultado idéntico" del spec: registros, versiones, disposiciones y totales.
3. **Cambiar el estado de una regla de significado entre dos cargas.** Se carga baseline, BRU-ESTADOS pasa a propuesta y se carga corrected.
   - `outstanding` no es un dato obligatorio, así que la carga sigue.
   - Silver deja los cuatro recibos `outstanding` de Brújula en *indeterminado*, con su etiqueta al lado. `R-101`, `paid`, sigue *pagado* por BRU-PORTAL.
   - El abierto conocido de Brújula / alder queda en 0.00 USD. Fuera de la suma quedan `R-100` (100.00), `R-102` (30.00) y `R-103`, sin monto utilizable. Birch queda en 0.00 USD, con un indeterminado de 80.00.
   - Silver entero se calculó con el estado nuevo, y la copia de reglas lo muestra. Las versiones no cambian.
   - Si BRU-ESTADOS vuelve a aceptada, la carga siguiente da otra vez 130.00 y 80.00 USD.
4. **Cambiar el estado de una regla con datos obligatorios.** AUR-01 pasa a propuesta. Aurora se queda sin piezas aplicables para sus datos obligatorios, así que la carga termina con error, dice cuáles faltan y no cambia nada. Borrar la base no lo arregla: la carga desde cero falla igual hasta que AUR-01 vuelva a estar aceptada.
5. **Cambiar una pieza que lee bronze.** El separador decimal de Aurora pasa de `,` a `.` entre dos cargas.
   - La guarda encuentra que el valor cambió y pide rehacer.
   - Al rehacer, en las dos tandas el manifest declara `,`, así que todas sus capturas quedan como "forma no reconocida" y no dan filas. Aurora sale de los totales.
   - Sus cuatro pólizas del book quedan "solo en el book", aunque la fuente sí mostró tres de ellas. Ver "Plan" al final.
   - Como la base se rehace desde cero, el orden de carga no cambia el resultado (CA-21).
6. **Escenarios `failure` y `drift`, cada uno en una base vacía.**
   - `failure`: la captura de la página 2 de recibos de alder falla con 503. Alder queda con 2 de 4 recibos y la captura incompleta (CA-03). El abierto conocido de alder es 100.00 USD.
   - `drift`: la página 2 trae los recibos bajo `items` y no bajo la llave que dice la pieza de BRU-OBSERVADO, así que queda como "forma no reconocida" (CD-07), con el mismo 2 de 4.
   - En los dos, las pólizas se leyeron completas.
7. **Las siete respuestas de CA-34 tienen de dónde leer.**

| Pregunta | De dónde lee |
|---|---|
| Cuánto está abierto y qué quedó fuera | silver, con la pieza que decidió cada disposición y cada estado |
| Historial de un recibo | Versiones de silver y apariciones de bronze |
| Pólizas en el book, en la fuente o en los dos | silver, y bronze para la referencia de cliente |
| Qué reglas tiene cada fuente y en qué estado | La copia de las reglas en silver |
| Valores con disposición distinta de válido | silver, con la pieza que decidió cada una |
| De qué campo sale cada nombre común | La copia de los descriptores: las piezas aplicables del diccionario, con su regla |
| Si cada captura quedó completa | La tabla de capturas de bronze |

8. **El orden de carga y la recarga (CA-21, CA-16)** no cambian respecto del ADR 0001: la copia de reglas no depende de qué tandas se cargan ni en qué orden.

**Lo que se gana**

- Un criterio de dos preguntas dice dónde va cada cosa que se sabe de una fuente, y lo que cambia una salida se ejecuta desde un solo lugar: las piezas aplicables.
- La base sigue siendo derivada entera; CA-04 se comprueba borrándola.
- La copia de las reglas y los valores de silver salen de la misma carga, así que no se contradicen.
- Toda pieza que se ejecuta apunta a la regla que la respalda, y toda regla apunta a su nota. De un total se llega a la nota que justifica cada exclusión.
- Un cambio de estado nunca deja registros sin identidad ni versiones sin orden.
- Un cambio de formato en una tanda de Aurora se ve, en vez de leerse mal.
- Una fuente nueva necesita sus tablas de bronze; lo demás que se sabe de ella va en su descriptor y sus reglas, y el código cambia solo si llega por un canal o con una forma que aún no sabe leer.

**Lo que cuesta**

- Un paso más en cada carga: leer los archivos de configuración, comprobarlos y copiarlos.
- La carga termina con error si un dato obligatorio no tiene exactamente una pieza aplicable o si cambió lo que lee bronze. Mientras tanto la base se queda como estaba, también para las demás fuentes.
- Para ver en la base un cambio de regla hay que cargar. Editar las tablas de la base no sirve.
- Un cambio en lo que lee bronze obliga a rehacer la base entera, no solo la fuente afectada.
- El historial de estados de una regla está en el historial del repositorio. "Qué estado tenía esta regla el día X" no se responde con una consulta.
- Quién decidió una regla es un texto escrito a mano. Nada impide que quien la propuso la acepte.
- El punto decimal de Brújula y el encabezado de los archivos se apoyan en una observación propia, no en algo que la fuente declare.
- La lista y los descriptores tienen un formato propio.

**Límites conocidos**

- Uno ocurre hoy: la nota de BRU-OBSERVADO es el ADR de extracción de Brújula, que todavía no existe.
- Cada dato se lee con una sola pieza por fuente. Si una fuente cambia de verdad su formato o la llave de sus respuestas, al cambiar la pieza y rehacer, las tandas anteriores quedan como "forma no reconocida" y su historial sale de silver (CA-22). Leer cada tanda con las piezas de su época pide reglas que valgan desde una fecha de la foto, no desde la fecha de la regla.
- La comparación del manifest cubre cinco valores. Una declaración nueva del manifest no se compara.
- Si la nota de una regla cambia de contenido, nada lo avisa.

**Lo que condiciona a las decisiones siguientes**

- *Extracción de Brújula.* Llena las piezas de BRU-OBSERVADO y es su nota: dónde vienen los registros, qué declara cada respuesta y los nombres de campo. Si elige las páginas HTML, cambian esas piezas, no este diseño.
- *Herramientas y almacenamiento.*
  - Un paso de código que lea la configuración, haga las comprobaciones y resuelva las piezas aplicables antes de leer capturas.
  - Que la copia, bronze y silver se escriban como una sola operación, o que se pueda deshacer si la carga falla.
  - Tablas que se reemplazan enteras; no hace falta modificar filas.
  - Si la herramienta guarda aparte de los datos una configuración cuyo cambio no obliga a recalcular, el estado de una regla no puede vivir ahí: tiene que estar en lo que la carga lee y copia.
- *Plan.*
  - El formato de la lista y de los descriptores, con los nombres de Frictionless donde existan.
  - Si las notas de las fuentes entran al repositorio junto con el lab.
  - Una opción de la carga para leer otra lista de reglas y otros descriptores, que necesita la prueba de CA-29.
  - La vista del book tiene que distinguir una póliza que la fuente no mostró de una que no se pudo leer, sin contar fallas que un reintento resolvió, para que CA-31 no diga algo falso. En Brújula, por broker; en Aurora, donde el broker es un dato de cada fila, por tanda.
  - En `make verificar`: la prueba de CA-29, que compara registros y disposiciones, no solo totales; que no haya dos piezas aplicables sobre la misma etiqueta o el mismo texto; que cada pieza cite una regla que existe y es de su misma fuente; que la nota de cada regla exista. Y tres pruebas con casos que el lab no trae, guardados fuera del lab porque el lab no se modifica: un manifest alterado, un dato obligatorio sin pieza y un cambio en lo que lee bronze.

## Referencias

Leídas el 2026-11-26. Respaldan partes de la decisión, no el conjunto.

- Frictionless, "Table Dialect" y "Table Schema": nombres para el separador, la coma decimal, el formato de fecha y los textos que significan "falta". https://datapackage.org/standard/table-dialect/ y https://datapackage.org/standard/table-schema/
- W3C, "Metadata Vocabulary for Tabular Data" (CSVW): separador, nulos y formato de fecha de un CSV. https://www.w3.org/TR/tabular-metadata/
- LinkML, "status": un campo de estado por elemento del esquema. https://linkml.io/linkml-model/latest/docs/status/
- OpenMetadata, aprobación de términos del glosario: lo que propone un agente entra como borrador y solo una persona lo aprueba. https://docs.open-metadata.org/latest/how-to-guides/data-governance/glossary/approval
- OpenMetadata, instalación local con Docker (al menos 6 GiB de memoria), y DataHub, guía rápida (8 GB): el tamaño de un catálogo. https://docs.open-metadata.org/v1.12.x/quick-start/local-docker-deployment y https://docs.datahub.com/docs/quickstart
