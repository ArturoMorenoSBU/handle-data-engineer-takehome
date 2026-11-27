# ADR 0001: Capas de la base compartida

- **Estado:** aceptada
- **Fecha:** 2026-11-27

## Contexto

Quien consulta los datos de un broker necesita ir de un total a lo que la aseguradora envió, y distinguir lo que la aseguradora dijo de cómo se leyó. Eso depende de cómo se organiza la base por dentro, y el spec (`specs/0001-base-compartida/SPEC.md`, sección 7) lo deja abierto: cuántas capas hay, qué guarda cada una y cómo se guardan las versiones de un registro. Una **capa** es un grupo de archivos o de tablas con una sola responsabilidad. Un **registro** es una póliza o un recibo. Los demás términos son los del spec (sección 2).

El spec sí fija lo que el diseño debe cumplir. Lo que llega se guarda tal como llegó (CA-01). Todo lo demás se puede rehacer desde ahí, sin volver a la fuente (CA-04). El orden de carga no cambia el resultado (CA-21). El monto, el vencimiento y el estado de cada recibo conservan su texto, su valor interpretado y su disposición (CA-08).

## Decisión

Cuatro capas; cada una se construye con las anteriores. Bronze, silver y gold son los nombres de la arquitectura [*medallion*](https://docs.databricks.com/aws/en/lakehouse/medallion), que ordena los datos de lo más crudo a lo más preparado; landing es el nombre habitual de la zona de archivos que queda antes. La última columna sigue un caso: el recibo `R-103` de alder en Brújula, cuyo monto llega como `TBD`.

| Capa | Qué guarda | Cómo se llena | El monto `TBD` |
|---|---|---|---|
| **landing** | Archivos: los bytes de cada captura tal como llegaron y, al lado, su contexto | Al capturar. No se modifica | La respuesta del portal, sin cambios |
| **bronze** | Lo que dijo cada fuente: tablas por aseguradora y una para el book, con los nombres de campo de la fuente y todos los valores como texto | Cada carga agrega lo que falta | `amount` con el texto `TBD` |
| **silver** | Lo compartido: pólizas, recibos y sus versiones, con nombres comunes. Del monto, el vencimiento y el estado: texto, valor interpretado y disposición | Se recalcula completa en cada carga | Texto `TBD`, valor vacío, disposición *no utilizable* por la regla CONTRACT-17 |
| **gold** | Una vista (una consulta guardada con nombre) por cada pregunta de CA-34 | Se calcula al consultar | Fuera del total, contado como "abierto sin monto utilizable" |

- **Landing es lo único que no es derivado.** Bronze, silver y gold forman la base de datos, que se borra y se rehace desde landing, con lo que se sabe de cada fuente. Las capturas se agrupan en **tandas**: las que se hacen de corrido contra una fuente para copiar una foto suya. Una base se construye con todas las tandas de su carpeta de landing.
- **Bronze no interpreta; silver sí.** Bronze guarda una fila por **aparición**: un registro tal como vino en una captura y en una posición dentro de ella. De cada campo guarda el texto y si no vino, vino vacío o vino como nulo explícito. Los datos propios de cada fuente (CA-15) se quedan ahí. Silver lee cada valor con los formatos y las reglas aceptadas de su fuente.
- **Una versión es una fila de silver.** En un recibo, una revisión con un contenido. Una póliza no trae revisión: empieza una versión cada vez que su contenido cambia de una foto a la siguiente. El contenido es el texto de bronze, no el valor interpretado.
- **Las versiones se ordenan por lo que declara la fuente**, no por el orden en que se cargó: la revisión en los recibos y la fecha de la foto en las pólizas. La última es la vigente (CA-20). Cada versión guarda su periodo, en fechas de foto: la primera donde se vio y la primera donde se vio una versión posterior. No dice cuándo cambió el registro entre dos fotos. Es la forma de una [dimensión de cambio lento tipo 2](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/type-2/) (SCD tipo 2), pero recalculada en cada carga en vez de mantenida fila por fila.

## Alternativas descartadas

- *Guardar las capturas dentro de la base, sin archivos.* Perder la base se llevaría lo único que no se puede volver a obtener: la fuente ya cambió.
- *Un solo paso, de la captura a las tablas compartidas.* Los campos que solo tiene una aseguradora tendrían que caber en ellas, y separar campos, leer formatos y aplicar reglas quedarían juntos.
- *Un paso más, con los valores interpretados por fuente antes de lo compartido.* Repite cada registro una vez más para los mismos tres valores.
- *Gold como modelo dimensional*, con tablas de eventos medibles y tablas con su contexto. Agrega más tablas que preguntas; silver ya cubre las consultas propias (CA-35).
- *Insertar en silver solo las versiones que faltan.* Cada valor quedaría leído con las reglas del día en que se insertó: si una regla cambia, silver mezcla dos lecturas y nada lo delata. Es el primer paso si el volumen lo pide.
- *SCD tipo 2 mantenido en cada carga, ordenado por la fuente.* Mismas respuestas sin reprocesar todo, pero modifica filas ya escritas y tiene el mismo problema con los cambios de regla. Es el segundo paso.
- *SCD tipo 2 mantenido en cada carga, ordenado por llegada.* Si la corrección se carga antes que el original, queda vigente la revisión vieja: 125.00 USD en vez de 130.00. No cumple CA-21.
- *Historial con dos ejes de tiempo* (cuándo lo dijo la fuente y cuándo se supo). Responde "qué sabíamos el día X", que el spec deja fuera de alcance.
- *Separar identidad y atributos al estilo Data Vault.* Más tablas y convenciones para nueve recibos.

## Consecuencias

Se gana:
- **Rehacer y cargar son la misma operación** (CA-04): leer todas las tandas de landing. Con las capturas guardadas sin cambios y pasos que reemplazan su salida completa, [todo lo demás se puede recalcular](https://maximebeauchemin.medium.com/functional-data-engineering-a-modern-paradigm-for-batch-data-processing-2327ec32c42a).
- **Ni el orden ni la recarga cambian el resultado** (CA-21, CA-16): silver sale de todo bronze, y cargar otra vez la misma tanda no le agrega nada. Nunca se modifican filas.
- **Silver nunca mezcla dos lecturas.** Si cambia una regla, la siguiente carga vuelve a leer todo con la regla nueva.
- **Una regla sobre el significado de un valor no altera lo que dijo la fuente** ni sus versiones: no llega a bronze, y las versiones se comparan por texto. Que una regla propuesta tampoco cambie silver (CA-29) depende de que silver aplique solo las aceptadas (CA-27).

Se pierde:
- **Recalcular silver completa no escala.** El tiempo de cada carga crece con todo el historial, no con lo nuevo. Con volumen se pasa al primer y al segundo paso de arriba; las capas y las respuestas no cambian.
- Los datos propios de cada fuente se leen en bronze, en tablas distintas por aseguradora: un paso más para quien escribe sus consultas.
- Los nombres de medallion traen expectativas: quien entienda silver como un modelo integrado esperará conversión de moneda o cruce de clientes, que aquí no existen. Se prefirieron a nombres propios porque quien conoce la arquitectura ubica cada capa.
- Un caso sin resolver, que no ocurre con los datos actuales: una revisión que no se puede leer como número se ordena hoy como si fuera 0. Hay que decidirlo antes de conectar una fuente real.
