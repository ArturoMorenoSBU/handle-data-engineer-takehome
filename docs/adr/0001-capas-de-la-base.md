# ADR 0001: Capas de la base compartida

- **Estado:** aceptada
- **Fecha:** 2026-11-27

## Contexto

Quien consulta los datos de un broker necesita poder confiar en una cifra: ir de un total a lo que la aseguradora envió, y distinguir lo que la aseguradora dijo de cómo se leyó. Eso depende de cómo se organiza la base por dentro.

El spec `specs/0001-base-compartida/SPEC.md` dice qué debe ser cierto de esa base y deja abierta su organización (sección 7): cuántas capas hay, cómo se llaman, qué guarda cada una, si las versiones de un registro se guardan o se recalculan, cómo se marca la versión vigente y dónde queda vacío un valor que no se pudo interpretar.

Una **capa** es un grupo de archivos o de tablas con una sola responsabilidad, que se construye a partir de las capas anteriores y de lo que se sabe de cada fuente. Este ADR usa los términos de la sección 2 del spec: aseguradora, broker, book, lab, captura, foto de la fuente, versión, versión vigente, disposición, regla y derivado. Un **registro** es una póliza o un recibo. Los criterios del spec se citan por su código: CA los obligatorios y CD los deseables (sección 3). Los términos que este ADR agrega se definen donde aparecen.

Cinco exigencias del spec condicionan el diseño:

- **No se controla la fuente.** Una respuesta puede fallar o cambiar de forma. Lo que llega se guarda tal como llegó (CA-01), y lo que no se reconoce se conserva y se hace visible (sección 5).
- **Todo lo derivado se puede rehacer** desde las capturas, sin volver a la fuente, con un resultado idéntico (CA-04).
- **El orden de carga no importa** (CA-21), y cargar dos veces lo mismo no cambia nada (CA-16).
- **El monto, el vencimiento y el estado de cada recibo conservan tres cosas:** el texto tal como llegó, el valor interpretado y su disposición (CA-08 a CA-10).
- **Lo propio de cada fuente no se traduce** (CA-15), y lo compartido se ofrece con los mismos nombres para las dos aseguradoras (CA-12).

## Decisión

Cuatro capas. Tres llevan los nombres de la arquitectura *medallion*, que ordena los datos de lo más crudo a lo más preparado: bronze, silver y gold. La cuarta es landing, el nombre habitual de la zona de archivos que queda antes de bronze. Cada quien usa esos nombres con un alcance distinto, así que aquí valen solo las definiciones de esta tabla.

| Capa | Qué guarda | Cómo se llena | Qué no hace |
|---|---|---|---|
| **landing** | Archivos. Por cada captura, los bytes tal como llegaron y, al lado, su contexto | Al capturar | No se modifica. No se consulta directamente |
| **bronze** | Lo que dijo cada fuente. Tablas separadas por aseguradora, y una para el book, con los nombres de campo de la fuente y todos los valores como texto | Cada carga agrega lo que falta | No interpreta valores |
| **silver** | Lo compartido. Pólizas, recibos y entradas del book con nombres comunes; las versiones de pólizas y recibos; y el texto, el valor interpretado y la disposición del monto, el vencimiento y el estado de cada recibo | Se recalcula completa en cada carga | No une registros de aseguradoras distintas ni convierte monedas |
| **gold** | Una vista por cada pregunta de CA-34. Una vista es una consulta guardada con nombre | No se llena: se calcula al consultar | No guarda datos propios |

Bronze, silver y gold forman la base de datos.

### landing

- De los datos de las fuentes, es lo único que no es derivado.
- Entran las respuestas de Brújula a las peticiones de pólizas y de recibos, incluidas las que fallan; los archivos de Aurora y su `manifest.json`; y el book. Los archivos que ya existen en el lab se copian, no se referencian. No entran contraseñas, sesiones ni la respuesta del inicio de sesión.
- El contexto de cada captura es el que pide CA-01: la fuente; el broker, cuando la captura es de uno solo; qué se pidió; cuándo; la fecha que declara la fuente; y si el intento falló y por qué. Se guarda junto a los bytes porque no siempre viene dentro de ellos: la respuesta de error 503 de Brújula no dice de qué broker ni de qué página es.
- Las capturas se agrupan en tandas. Una **tanda** es el conjunto de capturas que se hacen de corrido contra una fuente para copiar una foto suya. Cada captura guarda en su contexto a qué tanda pertenece, porque una respuesta fallida no trae fecha de foto. La fecha de foto de una tanda es la que declaran sus capturas exitosas. En Aurora, una tanda es el manifest y los archivos que lista para una versión de la entrega, y su fecha de foto es la que el manifest declara para esa versión; `policies.csv`, que está en las dos, se captura en las dos tandas. El book es una fuente más y se captura en su propia tanda.
- Cada captura y cada tanda tienen un identificador que se asigna al capturar y vive en landing. No depende de cuándo ni en qué orden se cargue.
- Un reintento es otra captura. Si una página falla dos veces y responde a la tercera, quedan tres capturas.
- **Una base corresponde a una carpeta de landing** y se construye con todas las tandas que hay en ella. Para tener una base con otro conjunto de tandas, como un escenario de falla aislado, se usa otra carpeta.
- Una **carga** agrega a bronze las tandas de la carpeta que bronze todavía no tiene y después recalcula silver. Se puede cargar tanda por tanda, en cualquier orden, o todas a la vez.

### bronze

- Una fila por **aparición**: un registro tal como vino en una captura y en una posición dentro de ella. En un archivo de Aurora la posición es la línea. La fila repetida de Aurora son dos filas de bronze.
- Para separar registros y campos usa solo la estructura que la fuente declara, como el separador y la codificación del manifest de Aurora. No lee decimales ni fechas, y no aplica ninguna regla sobre el significado de un valor.
- Guarda cada campo como texto y, además, si el campo no vino, vino con texto vacío o vino como nulo explícito. Una columna de texto sola no conserva esa diferencia, y CA-09 la necesita.
- Incluye una tabla de capturas con el contexto de landing, el resultado de cada captura y lo que la fuente declara de sí misma, como cuántas filas ofrece o qué archivos lista el manifest. Sirve para consultar de dónde salió cada fila (CA-02) y si la tanda quedó completa (CA-03). La completitud cuenta registros distintos, no apariciones.
- El resultado de una captura es uno de tres: se leyó; falló, con su causa; o respondió bien pero con una estructura que no se reconoce (CD-07). En los dos últimos casos hay fila en la tabla de capturas y ninguna fila de registros.
- Los datos propios de cada fuente (CA-15) viven aquí, con su nombre y su texto original.
- Cada carga agrega las apariciones que faltan. Una fila de bronze se identifica por su captura y su posición.

### silver

- Identifica cada póliza y cada recibo por aseguradora, broker y número (CA-05), y cada entrada del book por los mismos tres datos. Lo que identifica a cada fila de silver se calcula con datos de la fuente, no con un número consecutivo: la identidad del registro y, en una versión, su revisión y su contenido o, en una póliza, la fecha de la foto donde empieza.
- Es donde se interpreta cada valor: aquí entran los formatos que declara la fuente para decimales y fechas, y sus reglas aceptadas. Para el monto, el vencimiento y el estado de cada recibo guarda el texto original, el valor interpretado y la disposición. Si el valor no es válido, el valor interpretado queda vacío aquí; el texto sigue en silver y en bronze.
- Guarda las versiones (apartado "Versiones") y, por cada versión, todas las apariciones de bronze donde se observó (CA-02, CA-17, CA-22).
- **Se recalcula completa en cada carga**, leyendo todo bronze con lo que se sabe de cada fuente en ese momento. Son tablas que se reemplazan enteras: nada de silver sobrevive de una carga a la siguiente.
- Si hay más de una tanda del book, vale la capturada más tarde, porque el book no trae fecha propia.

### gold

- Cada vista lee de silver y de bronze: de silver lo compartido, y de bronze las capturas y los datos propios, como la fecha de pago en el historial de un recibo de Aurora o la referencia de cliente junto a la del book (CA-32). Las vistas de reglas y de diccionario de campos leen de donde se decida guardar las reglas. El diccionario de campos es la tabla que dice de qué campo de cada fuente sale cada nombre común (CA-13).
- No existe una columna de total general: la vista de totales agrupa por aseguradora, broker y moneda, así que no puede sumar monedas distintas (CA-23).
- Las consultas propias de CA-35 se escriben contra silver y bronze.

### Versiones

- **Qué es el contenido de un registro.** El texto de bronze de todos sus campos, incluidos los propios de la fuente y la marca de si cada campo no vino, vino vacío o vino como nulo explícito. No incluye la posición ni la fecha de la foto.
- **Qué es una versión.** En un recibo, una revisión con un contenido: la misma revisión con el mismo contenido en otra foto es la misma versión (CA-19). Una póliza no trae revisión: empieza una versión nueva cada vez que su contenido cambia respecto de la foto anterior donde apareció, aunque vuelva a uno que ya tuvo. Que una póliza falte en una foto no termina su versión. Como se compara el texto y no el valor interpretado, ninguna regla puede crear ni borrar una versión.
- **Cómo se guardan.** Una fila por versión en silver, con su **periodo observado** (*observada desde* y *observada hasta*) y la marca de vigente. Se calculan de nuevo en cada carga, junto con el resto de silver.
- **Cómo se ordenan.** Por lo que declara la fuente, no por el orden en que se cargó: la revisión en los recibos y la fecha de la foto en las pólizas. Para ordenar, silver lee la revisión como número y la fecha de la foto como instante, con su huso horario. La vigente es la última en ese orden (CA-20).
- **Qué significa el periodo.** *Observada desde* es la fecha y hora de la primera foto donde se vio la versión. *Observada hasta* es la de la foto más antigua donde se vio cualquier versión posterior en ese orden, y queda vacía en la vigente. Son fechas de foto: la fuente no dice cuándo cambió un registro entre dos fotos.
- **Datos propios de una versión.** Todas las apariciones de una versión tienen el mismo texto. Cada versión señala una como referencia: la primera por fecha de foto y, si empatan, por identificador de captura y posición. Por ella se leen los datos propios sin obtener filas repetidas.

Ejemplo: las versiones del recibo `R-102` de alder en Brújula, con las dos fotos del lab (`baseline` y `corrected`) cargadas en cualquier orden:

| Revisión | Monto | Observada desde | Observada hasta | Vigente |
|---|---|---|---|---|
| 1 | 25.00 | 2026-11-02 12:00 UTC | 2026-11-03 12:00 UTC | no |
| 2 | 30.00 | 2026-11-03 12:00 UTC | — | sí |

### Un valor que no se pudo interpretar, capa por capa

El ejemplo de Brújula usa sus respuestas en formato JSON y el nombre de campo que traen. Qué se captura de Brújula lo decide otro ADR; las capas no cambian.

| Caso | landing | bronze | silver | gold |
|---|---|---|---|---|
| Monto `TBD` de `R-103` (Brújula, alder) | Las respuestas de la página 2, sin cambios | `amount` con el texto `TBD` | Texto `TBD`, valor vacío, disposición *no utilizable* por la regla CONTRACT-17 | Fuera del total, contado como "abierto sin monto utilizable" |
| Vencimiento `31/11/2026` de `R-102` (Aurora, alder) | Los archivos de recibos, sin cambios | `vencimento` con el texto `31/11/2026` | Texto `31/11/2026`, valor vacío, disposición *inválido* | En la lista de valores con disposición distinta de válido |

## Alternativas descartadas

**Dónde vive la captura**

- *Los bytes en una columna de una tabla, sin archivos.* Una pieza menos, y una sola consulta llega de un total a los bytes que lo respaldan. Se descartó porque las capturas son lo único que no se puede volver a obtener: la fuente ya cambió. Si viven en la base, borrarla o perderla se las lleva.
- *Bytes en archivos y contexto solo en la base.* Al borrar la base se pierde el contexto de las capturas fallidas, que no está en los bytes.
- *Referenciar los archivos de Aurora y el book con su ruta, sin copiarlos.* Rehacer exigiría volver a leer la fuente, que es lo que CA-04 excluye.
- *Una sola carpeta de landing y una lista de qué tandas carga cada base.* Permite varias bases sobre las mismas capturas. Se descartó porque esa lista sería otro dato que no es derivado y que habría que guardar fuera de la base.

**Cuántos pasos entre la captura y lo compartido**

- *Un paso: de la captura directo a las tablas compartidas.* Menos tablas. Se descartó porque los campos que solo tiene una aseguradora tendrían que caber en las tablas compartidas, y porque separar campos, leer formatos y aplicar reglas quedarían en el mismo paso.
- *Tres pasos: texto por fuente, valores interpretados por fuente y, encima, lo compartido.* Separa los dos trabajos que aquí hace silver: interpretar y dar nombres comunes. Se descartó por tamaño: repite cada registro una vez más para los mismos tres valores con disposición.

**Forma de gold**

- *Un modelo dimensional, con tablas de eventos medibles y tablas con su contexto, y las vistas encima.* Sirve mejor a preguntas que hoy no están en la lista. Se descartó por tamaño: agrega más tablas que preguntas, las siete respuestas preparadas siguen haciendo falta, y cuatro de ellas (capturas, disposiciones, reglas y diccionario de campos) describen los datos, no el negocio. Pólizas, recibos y versiones en silver ya cubren las consultas propias.

**Nombres**

- *Nombres propios, por lo que guarda cada capa* (capturas, declarado, compartido, respuestas). Dicen qué hay adentro sin definición. Se prefirió el vocabulario de la arquitectura a uno propio: quien la conoce ubica cada capa. A cambio, hay que definir cada una, porque esos nombres traen expectativas distintas según quién los lea.

**Cómo se llena silver y cómo se guardan las versiones**

CA-18 a CA-20 piden una fila por versión y una sola vigente. Esa forma, con un periodo por fila, es la del patrón conocido como dimensión de cambio lento tipo 2 (SCD tipo 2). El periodo no lo pide ningún criterio obligatorio: lo usa el estado a un instante (CD-04), y sale del mismo cálculo. Las alternativas difieren en cómo se mantienen esas filas.

- *Insertar en silver solo las versiones que faltan y calcular el periodo y la vigente al consultar.* Cada carga procesa solo lo nuevo. Se descartó porque los valores interpretados quedarían guardados con las reglas del día en que se insertaron: si una regla cambia entre dos cargas, silver queda con dos lecturas mezcladas y nada lo delata. Evitarlo pide guardar con qué reglas se leyó cada fila y rehacer cuando cambien. Es el primer paso si el volumen lo pide.
- *SCD tipo 2 mantenido en cada carga, ordenado por la fuente.* El periodo y la vigente se guardan y cada carga los corrige solo para los registros que trae. Da las mismas respuestas sin reprocesar todo. Se descartó por tamaño: modifica filas ya escritas, obliga a comprobar que nunca queden dos vigentes y tiene el mismo problema con los cambios de regla. Es el segundo paso si el volumen lo pide.
- *SCD tipo 2 mantenido en cada carga, ordenado por llegada*, comparando lo que llega con la fila vigente. Si `corrected` se carga antes que `baseline`, la revisión 1 de `R-102` llega al final y queda como vigente: 125.00 USD en vez de 130.00. No cumple CA-21.
- *Tomar como vigente lo que trae la última foto donde aparece el registro.* Es lo que se hace con las pólizas, que no traen revisión. En un recibo, la vigente saldría de la fecha de la foto y no de la revisión, contra CA-20.
- *Historial con dos ejes de tiempo* (cuándo lo dijo la fuente y cuándo lo supimos). Responde "qué sabíamos el día X", que el spec deja fuera de alcance (sección 4).
- *Expresar el periodo con números de revisión en vez de fechas de foto.* Repite la revisión, significa cosas distintas en recibos y en pólizas, y no sirve para el estado a un instante (CD-04).
- *Separar en silver la identidad de cada registro de sus atributos por fuente, al estilo Data Vault.* Se descartó por tamaño: más tablas y convenciones para nueve recibos.

## Consecuencias

**Lo que se gana**

- **CA-04 se puede cumplir.** Rehacer la base y cargarla son la misma operación: leer todas las tandas de su carpeta de landing con lo que se sabe de cada fuente y no viene en sus capturas (las reglas, el diccionario de campos y la estructura de sus respuestas o archivos). El resultado es idéntico porque nada en la base depende de la hora en que se carga ni del orden de carga: los identificadores de captura y de tanda vienen de landing, y todo silver se calcula con bronze.
- **CA-21 se puede cumplir.** Silver se recalcula con todas las apariciones que hay en bronze, ordenadas por lo que declara la fuente. Ese conjunto es el mismo en cualquier orden de carga.
- **CA-16 se puede cumplir.** Cargar otra vez la misma tanda no agrega nada a bronze, y silver sale igual. Capturar de nuevo la misma foto crea otra tanda: agrega apariciones, pero ninguna versión, y no mueve los periodos, que son de foto.
- Silver nunca mezcla dos lecturas. Si cambia una regla, la siguiente carga vuelve a leer todo con la regla nueva.
- Ninguna regla sobre el significado de un valor llega a bronze, y las versiones se distinguen por el texto de bronze. Una regla, propuesta o aceptada, no puede alterar lo que dijo la fuente. Que una regla propuesta tampoco cambie silver (CA-29) depende de que silver aplique solo las aceptadas (CA-27).
- El estado a un instante (CD-04) es un filtro sobre las versiones: *observada desde* menor o igual al instante, y *observada hasta* vacía o mayor. Devuelve a lo sumo una versión por registro, y ninguna si el instante es anterior a la primera foto.
- No hace falta modificar filas: bronze solo agrega y silver se reemplaza entera.

**Lo que cuesta**

- **Recalcular silver completa en cada carga no escala.** El tiempo de cada carga crece con todo el historial, no con lo nuevo. Con los datos de esta prueba de concepto no se nota. Con volúmenes grandes hay que pasar a las dos primeras alternativas descartadas de versiones, en ese orden. Las capas y las respuestas no cambian; la forma de llenar silver sí.
- El texto de cada valor está en tres lugares: los bytes de landing, bronze y silver.
- Los datos propios de cada fuente se leen en bronze, en tablas distintas por aseguradora, a través de la aparición de referencia. Es un paso más para quien escribe sus consultas.
- El periodo observado no dice cuándo cambió el registro, solo en qué fotos se vio.
- Si cambia qué campos se leen de una fuente, o cómo se reconoce la estructura de sus respuestas, hay que rehacer también bronze: cambia el contenido de los registros, o una captura que no se reconocía pasa a dar filas.
- Los nombres de medallion traen expectativas. Quien entienda silver como un modelo integrado entre fuentes esperará conversión de moneda o cruce de clientes, que aquí no existen.

**Límites conocidos.** Ninguno ocurre con los datos del lab.

- Si una foto posterior trae una revisión menor que una ya vista en una foto anterior, la revisión menor queda con un periodo invertido: su *observada hasta* es anterior a su *observada desde*. La vigente no cambia (CA-20) y el filtro por instante nunca la devuelve.
- Si llegan dos contenidos distintos con la misma revisión (CD-08), el orden por revisión empata. Queda vigente el que se vio en la foto más reciente, y el caso se marca como anomalía. Si los dos vienen en la misma foto no hay desempate.
- Si una revisión no se puede leer como número, o una foto de una aseguradora no trae fecha, la versión se guarda marcada como no ordenable y el registro queda sin vigente. Se conserva y se ve, pero sale de los totales. Hay que decidir qué hacer con ese caso antes de conectar una fuente real.
- Si la fuente cambia a mitad de una tanda, sus capturas declaran dos fechas de foto. La tanda se marca como inconsistente.
- Un campo que la fuente empiece a mandar no entra a bronze, ni se ve en la base, hasta que se agrega a su tabla. Mientras tanto solo está en landing.

**Lo que condiciona a las decisiones siguientes**

- *Herramientas y almacenamiento.* Las capas piden archivos para landing y una base que agregue filas, reemplace tablas completas, ofrezca vistas y pueda ordenar las filas de un registro dentro de una consulta. No piden modificar filas ya escritas; el segundo paso para volúmenes grandes sí lo pediría. Una herramienta que arme el historial en cada corrida y no pueda rehacerlo desde landing no sirve.
- *Dónde viven las reglas.* Las reglas, el diccionario de campos y la estructura de cada fuente no salen de las capturas. Si se guardan en la base, esa parte de la base no es derivada y no se borra al rehacer. Vivan donde vivan, las vistas de reglas y de diccionario de campos necesitan poder leerlas desde la base.
- *Extracción de Brújula.* Lo que se capture entra a landing con la misma regla, y bronze necesita saber dónde vienen los registros en cada respuesta y cómo distingue la fuente un campo que no vino de un nulo explícito. Las versiones se comparan por texto, y la misma fuente puede mostrar un registro con textos distintos según se lea su respuesta JSON o su página HTML. Si se capturan las dos, hay que decir cuál alimenta a bronze.
- *Plan.* Quedan por decidir la estructura de carpetas de landing, si landing entra al repositorio y si silver guarda una columna por campo o una fila por campo.

## Referencias

Leídas el 2026-11-26. Respaldan partes de la decisión, no el conjunto.

- Databricks, "What is the medallion lakehouse architecture?": las tres capas bronze, silver y gold, y la recomendación de guardar los campos como texto en bronze. https://docs.databricks.com/aws/en/lakehouse/medallion
- Databricks, "Phase 6: Design Delta Lake architecture": la zona de archivos que recibe lo crudo antes de bronze. https://docs.databricks.com/aws/en/lakehouse-architecture/deployment-guide/delta-lake
- Maxime Beauchemin, "Functional Data Engineering" (2018): con los datos de origen guardados sin cambios y pasos que reemplazan su salida completa, todo lo demás se puede recalcular. https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a
- Kimball Group, "Type 2: Add New Row": una fila por cambio, con fecha de inicio, fecha de fin e indicador de fila vigente. Lo describe para tablas que se mantienen fila por fila; aquí se recalculan. https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/
- Databricks, "The AUTO CDC APIs": un SCD tipo 2 que se ordena por una columna de la fuente para aplicar bien los cambios que llegan fuera de orden. Es la referencia para la alternativa "ordenado por la fuente". https://docs.databricks.com/aws/en/ldp/cdc
- dbt, "Add snapshots to your DAG": los *snapshots* de dbt, que arman el historial comparando en cada corrida, no se pueden reconstruir si se pierden. https://docs.getdbt.com/docs/build/snapshots
