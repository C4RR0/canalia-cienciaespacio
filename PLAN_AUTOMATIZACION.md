# Plan de producción automática — Canal IA Ciencia y Espacio (+ Historia)

Este archivo es la referencia persistente del bucle autónomo (por si la sesión
se compacta o se reinicia). Léelo al despertar de cada ciclo antes de producir
el siguiente vídeo.

**Decisión 2026-09-19 (tarde):** el usuario pidió subir también contenido de
HISTORIA a este mismo canal, en vez de crear un canal aparte. La carpeta
`../CanalIA-Historia` queda SIN USAR (no se le sube nada, no tiene canal
propio autorizado) — todo el contenido, tanto de ciencia/curiosidades como
de historia, se produce y publica desde aquí, con `token.json` de este
proyecto. "Historia" pasa a ser una categoría de TEMA más a rotar, no un
formato ni un proyecto distinto.

## Decisiones ya acordadas con el usuario (2026-09-19)

- **Cadencia:** al máximo que permite la cuota gratuita de la API de YouTube
  (~6 subidas/día, 1 subida = 1600 unidades de las 10.000/día disponibles).
  No hace falta ir más rápido: mejor repartido a lo largo del día.
- **Contenido "infantil":** solo estética family-friendly (paleta de color
  `familiar` en `generar_diapositiva_lista.py`), NUNCA marcar `selfDeclaredMadeForKids: true`.
  Ya está fijado a `False` en `scripts/subir_youtube.py`.
- **Mecanismo:** todo corre dentro de esta sesión de Claude Code vía `/loop`,
  despertando periódicamente con `ScheduleWakeup`. Requiere el PC y esta
  ventana encendidos. Si la sesión se cierra, el bucle se detiene (no hay
  cron en la nube: no tiene acceso al sistema de archivos local, ffmpeg ni
  al token de YouTube).

## Mejora continua obligatoria (pedido explícito del usuario, reforzado 2026-09-19)

El usuario ha insistido varias veces: cada vídeo —de ciencia o de historia—
tiene que ser MÁS PROFESIONAL que el anterior, no solo distinto. Esto
significa, en cada iteración:
- Revisar aprendizajes.md antes de producir, para no repetir errores ya
  encontrados (imágenes irrelevantes, subtítulos tapados, duraciones falsas
  en el título, clips desincronizados, etc.)
- Buscar activamente qué se puede pulir en el guion, la elección de
  imágenes/clips, el ritmo, la miniatura — no conformarse con "que funcione",
  sino que se note mejor que el vídeo anterior del mismo formato.
- Cuando se detecte un problema de calidad (visual o de contenido), arreglar
  el CÓDIGO del pipeline si es sistémico, no solo el vídeo puntual.
- Esto aplica igual a historia que a ciencia/curiosidades — no es un
  criterio más laxo por ser una categoría de tema nueva.

## Categorías de TEMA a rotar

### Ciencia / curiosidades / naturaleza / espacio (la base del canal)
Curiosidades verificables de ciencia, animales, espacio, cuerpo humano, etc.
Ver ejemplos ya publicados en `temas_usados.txt`.

### Historia (nueva categoría, mismo canal, 2026-09-19)
Sucesos históricos, biografías, misterios resueltos, inventos que cambiaron
la historia. Mismas reglas técnicas de producción que ciencia, pero con
criterio editorial propio:
- **Precisión factual por encima de todo.** Contrastar fechas, nombres y
  cifras antes de escribir el guion — la desinformación histórica se
  disemina fácil y daña la credibilidad del canal a largo plazo.
- **Evitar encuadres políticamente unilaterales** en temas controvertidos
  (guerras, genocidios, conflictos religiosos, colonialismo, dictaduras del
  siglo XX). Presentar los hechos documentados, sin glorificar ni trivializar
  violencia o regímenes autoritarios, sin tomar partido en disputas
  historiográficas activas. En temas sensibles, preferir un ángulo
  humano/curiosidad concreta y verificable en vez de una interpretación
  política amplia (ejemplo ya publicado: short_012_stanislav_petrov, un
  hecho concreto y verificable, no un juicio sobre la URSS o EE.UU.).
- **Nada de negacionismo ni teorías marginales presentadas como hecho.** Si
  se menciona un mito o teoría desmentida, dejarlo marcado explícitamente
  como mito (igual que se hizo con la proyección de Mercator en ciencia).
- Wikimedia Commons es la mejor fuente de imágenes reales para historia
  (pinturas, fotografías de archivo, mapas históricos, todo dominio
  público). Cuidado especial con nombres propios homónimos (ver
  aprendizajes.md, short_012: Stanislav Petrov el militar vs. un futbolista
  búlgaro del mismo nombre) — el filtro de `buscar_imagenes_wikimedia.py` ya
  exige nombre+apellido en el título para estos casos, pero sigue haciendo
  falta revisar visualmente.

## Formatos a rotar (pide el usuario variedad: shorts, listas, largos, infantil, adultos)

**Prioridad actualizada 2026-09-20 con datos reales de audiencia** (ver
`aprendizajes.md`, análisis del 15:45): mientras el canal no tenga más
autoridad/suscriptores, priorizar `curiosidad` con diferencia sobre los
otros dos formatos — es el único que ha superado las 1000 vistas (varios
vídeos), frente a máximos de ~445 en `lista` y ~2 en `largo`. La variedad
de TEMA/estilo (punto 4 más abajo) sigue aplicando igual; lo que cambia es
la prioridad relativa de FORMATO.

1. **`curiosidad`** (short, ~45-70s): un dato sorprendente, guion de 4 párrafos,
   imágenes reales (Wikimedia/NASA). Formato ya probado desde el principio del canal.
   **Es el formato prioritario ahora mismo** — el único con tracción real.
2. **`lista`** (short, "25 cosas que no sabías en 1 minuto"): 25 datos rápidos
   sobre un tema, diapositivas generadas con número + texto. Validado
   2026-09-19 con `short_011_25_cuerpo_humano`, pero rendimiento muy por
   debajo de `curiosidad` en vídeos de edad comparable — hipótesis: al ser
   horizontal no encaja bien en el feed vertical nativo de Shorts. **Antes
   de producir más en horizontal, probar una versión VERTICAL del formato
   lista** para aislar si el problema es la orientación o el contenido.
3. **`largo`** (objetivo ampliado 2026-09-20: **15-30 min**, antes 8-20 min).
   **REACTIVADO 2026-09-20** a petición explícita del usuario ("meterle
   caña"), pese a que los 3 largos anteriores (agujeros negros, dinosaurios,
   viruela) tienen casi 0 vistas — el usuario decidió explícitamente
   aplicar aquí también la regla de tema extremo/poco manido en vez de
   parar el formato. Condiciones para que valga la pena esta vez:
   - **Tema**: mismo criterio que en `curiosidad` (ver más abajo) — extremo,
     poco conocido o con giro fuerte, NUNCA trivia genérica tipo "qué
     pasaría si caes en un agujero negro" (demasiado manido/abstracto).
   - **Título y miniatura**: cuidar especialmente, puede que el problema
     real de los 3 largos anteriores fuera ahí más que en el contenido —
     título con dato concreto y extremo, no genérico.
   - **Longitud del guion**: para 15-30 min reales de narración, ~3000-6500
     palabras (~18.000-40.000 caracteres) — contar caracteres antes de
     lanzar la producción, no basta con escribir "largo" a ojo (aprendido
     en largo_002, que salió de solo 3:14 por quedarse corto).
   - Revisar en unos días si estos nuevos largos remontan vistas frente a
     los anteriores, para confirmar si el problema era el tema/título o
     es estructural del formato en un canal sin audiencia todavía.
4. **Variación de audiencia/estilo** (usando `tema_visual` en el config, NO afecta
   `madeForKids`, solo estética):
   - `familiar`: colores vivos, temas más ligeros/positivos (animales, cuerpo
     humano, naturaleza, "sabías que...").
   - `adulto`: paleta oscura/elegante, temas más profundos o históricos
     (guerra, historia oscura, física compleja, true crime científico, etc.)
   - `espacio`, `naturaleza`, `historia`, `curiosidades`: paletas temáticas neutras.

## Cómo producir un vídeo (checklist por iteración)

1. Elegir un tema **no repetido** (revisar `temas_usados.txt`) y un formato
   distinto al del vídeo anterior (alternar curiosidad/lista/largo y
   familiar/adulto/neutro para dar variedad real).
   **Criterio de tema añadido 2026-09-20 (dato real, ver `aprendizajes.md`
   16:10):** con formato y edad iguales, el tema explicó una diferencia de
   13 a 1389 vistas. Preferir datos EXTREMOS, poco conocidos, o con un giro
   visual/narrativo fuerte (récords, biología rara, historias humanas
   dramáticas, sorpresas visuales) sobre trivia genérica ya muy repetida en
   internet (ej.: "por qué los flamencos son rosas", "la Muralla China no
   se ve desde el espacio" — correctos pero manidos). Si el tema elegido es
   de este segundo tipo, buscar un ángulo más extremo/específico o
   descartarlo por otro más fresco.
2. Escribir el contenido (guion o los 25 hechos) en español, con la voz y
   estilo ya establecidos (ver ejemplos en `guiones/`). Cuidar que sea
   **verificable y preciso** — no inventar datos falsos ni exagerar mitos
   (aprendizaje: se corrigieron ya 2 datos dudosos en `short_011`, ver
   `aprendizajes.md`).
   **Despedida obligatoria (pedido explícito del usuario, 2026-09-19):** todo
   guion (curiosidad, largo, y el "outro" de lista) debe terminar con una
   despedida natural que invite a seguir el canal para ver más contenido —
   nunca cortar justo tras el último dato. Debe sonar distinta cada vez,
   coherente con el tono del vídeo, no una frase genérica copia-pega. Ej.:
   "Si te ha sorprendido esto, sígueme para más curiosidades como esta" /
   "Cuéntame en los comentarios si lo sabías, y sígueme si quieres más datos
   así" — variar la redacción vídeo a vídeo. El pipeline ya añade además
   ~0.8s de silencio final automáticamente (`anadir_silencio_final` en
   `producir_video.py`) para que el corte no sea brusco justo tras hablar.
   **Regla de honestidad en el título:** no prometer "(en 1 minuto)" salvo que
   la duración real vaya a ser &lt;70s (con 25 datos a ritmo normal de voz
   la duración real ronda 1:30-1:50). Preferir títulos tipo "25 cosas que no
   sabías sobre X" sin promesa de tiempo, o reducir a ~12-15 datos si se
   quiere que "1 minuto" sea literalmente cierto.
   **Investigación de palabras clave (añadido 2026-09-20, pedido explícito
   del usuario):** antes de fijar título/descripción/tags, comprobar qué
   busca la gente de verdad con el autocompletado de búsqueda de YouTube
   (gratis, sin API key):
   `curl "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=es&gl=es&q=<tema+en+español>"`
   — probar 2-3 variantes del tema (nombre corto, con "curiosidad"/"dato",
   etc.), mirar las sugerencias reales que devuelve, e incorporar de forma
   NATURAL las que tengan sentido en el título, la descripción, **los tags
   de metadatos (campo `tags`) Y los hashtags visibles al final de la
   descripción** — son dos cosas distintas, hay que actualizar las dos
   (aprendido 2026-09-20: la primera pasada solo tocó los tags, se olvidaron
   los hashtags visibles). No forzar keywords que no encajen (evitar que
   suene raro solo por meter una palabra clave) — la legibilidad para el
   espectador va primero.
3. Escribir el config JSON en `produccion_config/<id>.json` (ver ejemplos:
   `short_010_camaron_mantis.json` para curiosidad, `short_011_25_cuerpo_humano.json`
   para lista).
4. Ejecutar: `python scripts/producir_video.py produccion_config/<id>.json`
   (hace TODO el proceso, incluida la subida real a YouTube pública).
5. Revisar con la herramienta Read la miniatura generada
   (`salidas/miniatura_<id>.jpg`) Y ADEMÁS 2-3 de las imágenes reales usadas
   (`imagenes/<id>/img_XX.jpg`), para detectar tanto problemas visuales de la
   miniatura como imágenes de contenido irrelevante (ver aprendizajes.md,
   short_012: una búsqueda de un nombre propio devolvió la foto de un
   futbolista homónimo, y otra devolvió un pez de arrecife — ya mitigado con
   un filtro de relevancia en `buscar_imagenes_wikimedia.py`, pero no es
   infalible, así que sigue haciendo falta la revisión visual).
6. Anotar en `temas_usados.txt` el tema usado.
7. Anotar en `aprendizajes.md` qué se probó, qué salió bien/mal, y qué se
   cambia para el siguiente (código o criterio editorial).
8. Cada pocas iteraciones (cuando ya haya vídeos con &gt;=48h desde publicación),
   ejecutar `python scripts/analizar_video.py` para ver vistas/retención reales
   y usarlas para decidir qué temas/formatos repetir.
9. Programar el siguiente despertar con `ScheduleWakeup` espaciado para no
   superar ~6 subidas/día (repartidas, no todas seguidas).
10. **Avisar con `PushNotification` en cuanto se publique CADA vídeo nuevo**
    (pedido explícito del usuario, 2026-09-20), no solo ante bloqueos
    (`uploadLimitExceeded`/`quotaExceeded`) — un mensaje corto con título y
    URL del vídeo basta.

## Límite de subidas diarias (uploadLimitExceeded)

Descubierto el 2026-09-19: además de la cuota de la API (que aguantó bien,
~12 subidas en un día sin problema), YouTube tiene un límite propio de
NÚMERO de vídeos que un canal sin verificar por teléfono puede subir en un
periodo. Al superarlo, la API devuelve HTTP 400 "uploadLimitExceeded", no
"quotaExceeded". Cuando esto pase: no reintentar en bucle (seguirá
fallando), dejar el vídeo ya generado en `salidas/` para subirlo más
adelante, anotarlo en aprendizajes.md, y esperar antes de la siguiente
producción. Verificar el canal por teléfono (https://www.youtube.com/verify)
probablemente también solucione esto, igual que ya se sabe que soluciona lo
de las miniaturas personalizadas.

## Nota sobre miniaturas personalizadas

El canal aún no está verificado por teléfono en YouTube, así que
`youtube.thumbnails().set()` devuelve 403 (esto ya no rompe la subida, ver
`scripts/subir_youtube.py`, solo se queda sin miniatura personalizada). En
cuanto el usuario verifique el canal en https://www.youtube.com/verify, se
puede re-aplicar la miniatura de cada vídeo ya publicado con
`python scripts/poner_miniatura.py <video_id> <salidas/miniatura_xxx.jpg>`.
Las miniaturas ya generadas no se pierden, quedan en `salidas/`.

## Estado de la cuota de la API

10.000 unidades/día por defecto. Subir 1 vídeo = ~1600 unidades. Con otras
llamadas (listar, analizar, comprobar monetización) hay margen holgado para
~6 subidas/día. Si en algún momento la cuota se agota, el error de la API lo
dirá explícitamente (quotaExceeded) — en ese caso, esperar al día siguiente
(la cuota se resetea a medianoche hora del Pacífico) y anotarlo en
`aprendizajes.md`.
