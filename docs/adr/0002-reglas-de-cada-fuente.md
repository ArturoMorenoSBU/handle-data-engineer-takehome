# ADR 0002: Dónde vive lo que se sabe de cada fuente

- **Estado:** aceptada
- **Fecha:** 2026-11-27

## Contexto

Quien integra una aseguradora aprende cosas que cambian cómo se leen sus datos: que sus archivos van separados por `;`, que `TBD` en un monto no es cero, que `EM_ABERTO` quiere decir abierto. Si ese conocimiento queda repartido en el código o en la cabeza de alguien, se pierde en la siguiente integración, o se aplica algo que nadie aceptó. Leer `TBD` como cero, una propuesta sin verificar, haría pasar un total incompleto por completo.

El spec (`specs/0001-base-compartida/SPEC.md`) llama **regla** a cada cosa de esas. Pide que cada una tenga estado, origen, fecha, quién la propuso o la aceptó y una nota que la respalde (CA-26); que solo se apliquen las aceptadas (CA-27); que nunca se elija entre reglas por su fecha (CA-28); y que una regla propuesta no cambie ningún resultado (CA-29). Deja abierto dónde viven las reglas y qué va en código, en datos, en configuración o en memoria (sección 7). Las capas (landing, bronze, silver, gold) y las tandas son las del ADR 0001.

## Decisión

Cada cosa que se sabe de una fuente va a uno de cuatro lugares. Se decide con dos preguntas: ¿puede cambiar lo que la carga escribe en bronze o en silver? Y si puede, ¿vale igual para toda fuente, cambia por fuente o llega con cada captura?

| Lugar | Qué va | Ejemplos |
|---|---|---|
| **Código** | Lo que vale igual para toda fuente y no debe poder apagarse | Una fecha que no existe queda *inválida* y no se repara. Una página fallida no es una página vacía |
| **Configuración** | Lo que cambia por fuente | La lista de reglas y el descriptor de cada fuente |
| **Datos** | Lo que llega con cada captura | Las capturas de landing, incluido el `manifest.json` de Aurora |
| **Memoria** | Lo que explica y no cambia ningún resultado. La carga nunca la lee | Las notas de las fuentes, el spec, los ADRs y las instrucciones que leen los agentes |

- **La configuración son dos clases de archivo del repositorio.** La **lista de reglas** tiene una fila por regla, con los datos de CA-26: dice qué se sabe y con qué autoridad. El **descriptor** de cada fuente es un conjunto de **piezas**: instrucciones concretas que la carga ejecuta, como "el separador es `;`" o "`EM_ABERTO` es *abierto*". Cada pieza cita una regla. Hoy son diez reglas y tres descriptores: Brújula, Aurora y el book.
- **Una pieza se aplica solo si su regla está aceptada**; esas son las **piezas aplicables**. Un paso de código las resuelve antes de leer capturas, y bronze y silver calculan solo con ellas. La fecha de una regla no entra en ningún cálculo. Ejemplo: dos reglas de Brújula tienen una pieza sobre `TBD` en el monto. La de CONTRACT-17, aceptada, lo deja *no utilizable*. La de AGENT-22, propuesta, lo leería como cero: queda registrada, se puede consultar y no se aplica.
- **Qué dice un descriptor.** Piezas de estructura: cómo se separan registros y campos; las usa bronze. Piezas de formato y de significado: cómo se leen decimales y fechas, de qué campo sale cada nombre común y qué quiere decir cada etiqueta de estado; las usa silver. Los datos sin los que una fuente no se puede leer, como el separador o los campos de la identidad, son **datos obligatorios**: cada uno necesita exactamente una pieza aplicable, o la carga termina con error antes de escribir nada. Una etiqueta de estado sin pieza aplicable queda *indeterminada*.
- **El original vive en archivos y silver tiene una copia.** Cada carga copia la lista y los descriptores a tablas de silver, que se reemplazan con el resto de silver. Lo que la base muestra de las reglas es siempre aquello con que se calculó, y la base sigue siendo derivada entera.
- **El formato de Aurora se declara dos veces:** en su guía (regla AUR-01) y en el manifest de cada tanda. Bronze solo lee una tanda cuando las dos coinciden; si no, sus capturas quedan como "forma no reconocida" (CD-07) y no dan filas.
- **La memoria informa y no se ejecuta.** Vale para las notas de la organización y para las de los agentes. Si algo escrito en una nota debe cambiar un resultado, se escribe como regla, con estado y con piezas.

## Alternativas descartadas

- *La base como original de las reglas, en tablas que no se borran al rehacer.* Construir desde cero (CA-33) pide de todos modos un archivo con las reglas iniciales, que sería un segundo original, y CA-04 ya no se comprobaría borrando la base.
- *Un catálogo de datos con flujo de aprobación*: una aplicación donde se registran los datos, su significado y sus dueños. Es el paso siguiente si varias personas proponen y aceptan reglas. Pide de [6](https://docs.open-metadata.org/v1.12.x/quick-start/local-docker-deployment) a [8 GB](https://docs.datahub.com/docs/quickstart) de memoria y varios servicios, y el spec deja fuera el flujo de aprobación.
- *Un estándar para escribir la lista y los descriptores*, como [Frictionless](https://datapackage.org/standard/table-dialect/), CSVW o LinkML. Ninguno aplica el estado al transformar: el filtro de lo aceptado sería código propio igual. Sus nombres se pueden usar dentro del formato propio.
- *El formato de Aurora de un solo lado.* Solo del descriptor, un cambio de formato se leería mal sin aviso: si una entrega pasa a punto decimal, `1.500` sería uno y medio y se leería como mil quinientos. Solo del manifest, una diferencia con la guía se resolvería en silencio a favor del manifest.
- *El significado de los estados en el código de silver.* Lo que está en el código siempre se ejecuta: un mapeo propuesto no podría quedar sin aplicar (CA-27).
- *Lo propuesto sin pieza; aceptar una regla sería escribir su pieza.* Deja dos marcas de lo mismo, la ubicación y el estado, que pueden contradecirse. Y CA-29 se cumpliría sin que el filtro se ejerza.
- *Precedencia por autoridad*: el contrato antes que la documentación, y esta antes que una propuesta. Decidiría sola conflictos que conviene ver.
- *Que la carga lea las notas.* Un cambio de redacción podría mover un resultado.

## Consecuencias

Se gana:
- Lo que cambia un resultado se ejecuta desde un solo lugar, las piezas aplicables, y nada propuesto llega a la carga (CA-27, CA-29).
- De un total se llega a la nota que justifica cada exclusión: el valor apunta a su pieza, la pieza a su regla y la regla a su nota (CD-01, CA-26).
- La base sigue siendo derivada entera: CA-04 se comprueba borrándola. Las reglas que muestra y los valores de silver salen de la misma carga, así que no se contradicen.
- Una fuente nueva pide sus tablas de bronze, su descriptor y sus reglas. El código cambia solo si llega por un canal o con una forma que aún no sabe leer.

Se pierde:
- La carga termina con error si un dato obligatorio no tiene exactamente una pieza aplicable. Mientras tanto la base se queda como estaba, también para las demás fuentes.
- Un cambio en lo que lee bronze, como el separador, obliga a rehacer la base entera: la carga lo detecta y termina con error.
- Para ver en la base un cambio de regla hay que cargar. El historial de estados de una regla está en el historial del repositorio, no en una consulta.
- Quién decidió una regla es un texto escrito a mano: nada impide que quien la propuso la acepte.
- Cada dato se lee con una sola pieza por fuente. Si una fuente cambia de verdad su formato, las tandas anteriores dejan de leerse y su historial sale de silver (CA-22).
