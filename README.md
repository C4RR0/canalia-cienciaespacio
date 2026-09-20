# Canal IA — Ciencia y Espacio (curiosidades)

Canal de YouTube automatizado con IA, en español, sobre curiosidades de ciencia y espacio.
Formatos: Shorts (<60s) y vídeos largos (8-20 min).

## Stack (100% gratuito para empezar)

| Paso | Herramienta | Script |
|---|---|---|
| Guion | Escrito por Claude | `guiones/*.txt` |
| Voz (TTS) | edge-tts (voces neuronales de Microsoft, gratis) | `scripts/generar_audio.py` |
| Imágenes IA | Pollinations.ai (gratis, sin API key) | `scripts/generar_imagenes.py` |
| Ensamblado de vídeo | ffmpeg (zoom/pan tipo Ken Burns) | `scripts/ensamblar_video.py` |
| Subtítulos | (pendiente: faster-whisper) | `scripts/generar_subtitulos.py` |

## Estructura de carpetas

```
guiones/     -> guiones de texto, uno por vídeo
audio/       -> narraciones generadas (.mp3)
imagenes/    -> imágenes IA generadas, una subcarpeta por vídeo
subtitulos/  -> archivos .srt generados
videos/      -> clips intermedios
salidas/     -> vídeos finales listos para subir
scripts/     -> pipeline en Python
```

## Flujo de trabajo por vídeo

1. Escribir el guion en `guiones/nombre.txt`
2. Generar audio: `python scripts/generar_audio.py guiones/nombre.txt audio/nombre.mp3`
3. Generar prompts de imágenes (uno por escena) y generarlas:
   `python scripts/generar_imagenes.py imagenes/prompts_nombre.txt imagenes/nombre 1024 1792` (vertical, shorts)
   `python scripts/generar_imagenes.py imagenes/prompts_nombre.txt imagenes/nombre 1792 1024` (horizontal, largos)
4. Ensamblar vídeo: `python scripts/ensamblar_video.py imagenes/nombre audio/nombre.mp3 salidas/nombre.mp4 1080 1920`
5. (Pendiente) Generar subtítulos y quemarlos en el vídeo
6. Subir a YouTube (manual por ahora)

## Notas de la voz

Voces en español probadas con edge-tts:
- `es-ES-AlvaroNeural` (hombre, España, tono narrativo) — usada por defecto
- `es-ES-ElviraNeural` (mujer, España)
- `es-MX-JorgeNeural` / `es-MX-DaliaNeural` (acento latino)

## Próximos pasos

- [ ] Subtítulos automáticos quemados en vídeo (faster-whisper)
- [ ] Generación de miniaturas
- [ ] Plantilla de intro/outro de marca
- [ ] Banco de 20-30 guiones para primer lote
- [ ] Automatizar subida vía YouTube Data API
- [ ] Calendario de publicación
