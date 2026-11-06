# QA manual de fotos (cuando un Short se queda en pendientes_qa.txt)

Se ejecutan desde una carpeta de trabajo fuera del repo (p. ej. %TEMP%\qa_sabiasque):

1. `python <repo>/scripts/qa_manual/cand.py <id> "query 1" "query 2" ...` → baja hasta 20 candidatas de Commons a <id>/cNN.jpg y hace <id>/hoja.jpg (hoja de contactos) + titulos.json.
2. `python <repo>/scripts/qa_manual/dl.py <carpeta> "File:Titulo exacto.jpg" ...` → baja ficheros concretos de Commons (x0.jpg, x1.jpg…).
3. Mirar las hojas y elegir 5-8 fotos REALES del tema (sin heridas, cadáveres, mapas ni láminas).
4. `python <repo>/scripts/qa_manual/fin.py <id> foto1.jpg foto2.jpg ...` → rellena img_01-08 (repite si hay menos de 8), _reales.json, miniatura con la PRIMERA foto y quita el id de pendientes_qa.txt.
5. Mirar la miniatura y hacer commit + push.

Commons da 429 con frecuencia: lanzar las descargas en segundo plano.
