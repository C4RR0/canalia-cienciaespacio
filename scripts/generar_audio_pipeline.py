"""
Prepara EN LOCAL los medios que la nube no puede generar por si misma
(audio TTS e imagenes reales), porque tanto edge-tts como Wikimedia/NASA/
Pollinations quedan bloqueados por la whitelist de dominios del proxy de
seguridad del sandbox cloud (ver aprendizajes.md 2026-09-20 y 2026-09-21).

Deja el audio en cola_audio/<id>_final.mp3 y las imagenes en
cola_imagenes/<id>/img_XX.jpg (+ un _reales.json con que imagenes son
fotos reales vs respaldo IA) para que la nube (producir_video.py) los
recoja y complete el resto del pipeline (ensamblado, subtitulos,
miniatura, subida) sin volver a tocar TTS ni buscadores de imagenes.

Uso:
    python generar_audio_pipeline.py produccion_config/<id>.json
"""
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from pydub import AudioSegment

BASE = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))

import generar_audio
import suavizar_audio
import generar_subtitulos
import corregir_subtitulos
import generar_subtitulos_ass_palabras
import generar_miniatura
import ensamblar_lista_horizontal as ensamblador_lista
import producir_video


def log(msg: str):
    print(f"\n=== {msg} ===", flush=True)


def anadir_silencio_final(audio_path: Path, ms: int = 800):
    audio = AudioSegment.from_file(audio_path)
    (audio + AudioSegment.silent(duration=ms)).export(audio_path, format="mp3", bitrate="192k")


def construir_texto_lista(cfg: dict) -> str:
    partes = [cfg["intro"].strip()]
    for hecho in cfg["hechos"]:
        partes.append(hecho.strip())
    partes.append(cfg["outro"].strip())
    return "\n\n".join(partes)


def generar_audio_para_config(cfg: dict) -> Path:
    vid = cfg["id"]
    formato = cfg["formato"]
    voz = cfg.get("voz", "es-ES-AlvaroNeural")

    dir_guiones = BASE / "guiones"
    dir_audio = BASE / "audio"
    dir_cola = BASE / "cola_audio"
    for d in (dir_guiones, dir_audio, dir_cola):
        d.mkdir(exist_ok=True)

    log("1/2 Guion")
    if formato == "lista":
        texto_guion = construir_texto_lista(cfg)
    else:
        texto_guion = cfg["guion"].strip()
    guion_path = dir_guiones / f"{vid}.txt"
    guion_path.write_text(texto_guion, encoding="utf-8")
    print(f"Guion escrito: {guion_path} ({len(texto_guion)} caracteres)")

    if formato == "lista":
        log("2/2 Audio (TTS + suavizado, por segmento)")
        segmentos_texto = [cfg["intro"].strip()] + [h.strip() for h in cfg["hechos"]] + [cfg["outro"].strip()]
        dir_audio_seg = dir_audio / f"{vid}_segmentos"
        dir_audio_seg.mkdir(parents=True, exist_ok=True)
        rutas_segmentos = []
        for i, texto in enumerate(segmentos_texto):
            seg_txt = dir_audio_seg / f"seg_{i:02d}.txt"
            seg_bruto = dir_audio_seg / f"seg_{i:02d}_bruto.mp3"
            seg_final = dir_audio_seg / f"seg_{i:02d}.mp3"
            seg_txt.write_text(texto, encoding="utf-8")
            if not seg_final.exists():
                asyncio.run(generar_audio.generar(str(seg_txt), str(seg_bruto), voz))
                suavizar_audio.suavizar(str(seg_bruto), str(seg_final))
            rutas_segmentos.append(seg_final)

        ffmpeg_bin, ffprobe_bin = ensamblador_lista.resolver_bin()
        duraciones_segmentos = [ensamblador_lista.duracion_audio(ffprobe_bin, str(p)) for p in rutas_segmentos]

        audio_final = dir_audio / f"{vid}_final.mp3"
        lista_concat = dir_audio_seg / "lista_concat.txt"
        lista_concat.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in rutas_segmentos), encoding="utf-8"
        )
        subprocess.run([ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(lista_concat),
                         "-c", "copy", str(audio_final)], check=True, capture_output=True)
        print(f"Audio concatenado ({len(rutas_segmentos)} segmentos): {audio_final}")

        duraciones_clips = list(duraciones_segmentos[1:-1])
        duraciones_clips[0] += duraciones_segmentos[0]
        duraciones_clips[-1] += duraciones_segmentos[-1]

        SILENCIO_FINAL_MS = 800
        anadir_silencio_final(audio_final, SILENCIO_FINAL_MS)
        duraciones_clips[-1] += SILENCIO_FINAL_MS / 1000

        meta_path = dir_cola / f"{vid}_duraciones.json"
        meta_path.write_text(json.dumps(duraciones_clips), encoding="utf-8")
    else:
        log("2/2 Audio (TTS + suavizado)")
        audio_bruto = dir_audio / f"{vid}_bruto.mp3"
        audio_final = dir_audio / f"{vid}_final.mp3"
        asyncio.run(generar_audio.generar(str(guion_path), str(audio_bruto), voz))
        suavizar_audio.suavizar(str(audio_bruto), str(audio_final))
        anadir_silencio_final(audio_final, 800)

    destino = dir_cola / f"{vid}_final.mp3"
    destino.write_bytes(audio_final.read_bytes())
    print(f"Audio listo para la nube: {destino}")
    return destino


def generar_imagenes_para_config(cfg: dict) -> Path | None:
    """Solo aplica a formato curiosidad/largo (queries_imagenes). El formato
    'lista' usa clips de vídeo de Pexels, no imagenes fijas, y Pexels no
    tiene (de momento) el mismo bloqueo confirmado en el sandbox cloud."""
    vid = cfg["id"]
    if cfg["formato"] == "lista":
        print("Formato 'lista': no usa queries_imagenes, nada que encolar aquí.")
        return None

    fuente = cfg.get("fuente_imagenes", "wikimedia")
    dir_imagenes = BASE / "imagenes"
    dir_cola_img = BASE / "cola_imagenes" / vid
    dir_cola_img.mkdir(parents=True, exist_ok=True)

    log("Imágenes reales (Wikimedia/NASA + respaldo IA)")
    carpeta_raw = dir_imagenes / vid
    rutas = producir_video.obtener_imagenes_reales(cfg["queries_imagenes"], carpeta_raw, fuente)
    if not rutas:
        raise RuntimeError("No se consiguió ninguna imagen para el vídeo.")

    reales_flags = []
    for i, (ruta, es_real) in enumerate(rutas, start=1):
        destino = dir_cola_img / ruta.name
        destino.write_bytes(ruta.read_bytes())
        reales_flags.append(es_real)
    meta_path = dir_cola_img / "_reales.json"
    meta_path.write_text(json.dumps(reales_flags), encoding="utf-8")
    print(f"{len(rutas)} imágenes listas para la nube en: {dir_cola_img}")
    return dir_cola_img


def generar_subtitulos_para_config(cfg: dict, audio_final: Path) -> Path | None:
    """Transcribe y corrige los subtítulos EN LOCAL (faster-whisper necesita
    descargar su modelo de Hugging Face Hub la primera vez, y ese dominio
    también está bloqueado por la whitelist del sandbox cloud — ver
    aprendizajes.md 2026-09-21 tarde) y deja el .srt ya corregido listo en
    cola_subtitulos/<id>_corregido.srt para que la nube lo reutilice sin
    necesitar red para nada de transcripción."""
    if cfg["formato"] == "lista":
        print("Formato 'lista': no usa transcripción por whisper, nada que encolar aquí.")
        return None

    vid = cfg["id"]
    dir_subs = BASE / "subtitulos"
    dir_cola_subs = BASE / "cola_subtitulos"
    dir_subs.mkdir(exist_ok=True)
    dir_cola_subs.mkdir(exist_ok=True)

    log("Subtítulos (transcripción whisper + corrección, en local)")
    srt_crudo = dir_subs / f"{vid}.srt"
    generar_subtitulos.generar_srt(str(audio_final), str(srt_crudo), "small")

    srt_corregido = dir_subs / f"{vid}_corregido.srt"
    correcciones = cfg.get("correcciones_subtitulos")
    correcciones_path = None
    if correcciones:
        correcciones_path = dir_subs / f"correcciones_{vid}.txt"
        correcciones_path.write_text(
            "\n".join(f"{k}|{v}" for k, v in correcciones.items()), encoding="utf-8"
        )
    corregir_subtitulos.corregir(str(srt_crudo), str(srt_corregido), correcciones_path)

    destino = dir_cola_subs / f"{vid}_corregido.srt"
    destino.write_bytes(srt_corregido.read_bytes())

    # Subtítulos animados palabra-por-palabra (estilo viral), a partir del
    # sidecar de timestamps por palabra que generar_subtitulos.py deja junto
    # al .srt crudo. Es el formato que usa quemar_subtitulos.py por defecto
    # ahora; el .srt de arriba se conserva como respaldo/legible.
    ancho, alto = (1080, 1920) if cfg.get("orientacion", "vertical") == "vertical" else (1920, 1080)
    palabras_json = srt_crudo.with_name(srt_crudo.stem + "_palabras.json")
    ass_corregido = dir_subs / f"{vid}_corregido.ass"
    generar_subtitulos_ass_palabras.generar(palabras_json, ass_corregido, ancho, alto, correcciones_path,
                                           guion=cfg.get("guion"))
    destino_ass = dir_cola_subs / f"{vid}_corregido.ass"
    destino_ass.write_bytes(ass_corregido.read_bytes())

    print(f"Subtítulos listos para la nube: {destino} (+ {destino_ass})")
    return destino


def generar_miniatura_para_config(cfg: dict) -> Path | None:
    """Miniatura con imagen IA cinematográfica dedicada (Pollinations), no un
    fotograma del propio vídeo: mucho más impactante (ver aprendizajes.md
    2026-09-22). Pollinations está bloqueado por la whitelist del sandbox
    cloud igual que Wikimedia/NASA/Azure, así que se genera aquí en local y
    viaja por cola_miniaturas/<id>.jpg. Solo aplica a curiosidad/largo (el
    formato 'lista' ya tiene su propia miniatura de diapositiva dedicada,
    generada sin red, en producir_video.py)."""
    vid = cfg["id"]
    if cfg["formato"] == "lista":
        print("Formato 'lista': ya genera su propia miniatura sin red, nada que encolar aquí.")
        return None

    dir_cola_mini = BASE / "cola_miniaturas"
    dir_cola_mini.mkdir(exist_ok=True)
    destino = dir_cola_mini / f"{vid}.jpg"

    log("Miniatura IA cinematográfica")
    hook = cfg.get("hook_miniatura", cfg["titulo"][:60])
    # prompt_miniatura evita que la IA invente la cara de una persona real
    # cuando la primera query es un nombre propio (p. ej. "Vesna Vulovic").
    sujeto_visual = cfg.get("prompt_miniatura") or cfg["queries_imagenes"][0]
    orientacion = cfg.get("orientacion", "vertical" if cfg["formato"] != "largo" else "horizontal")
    semilla = abs(hash(vid)) % 100000
    try:
        generar_miniatura.generar_desde_ia(sujeto_visual, hook, str(destino), orientacion, semilla=semilla)
    except Exception as e:
        # 15/10: Pollinations da 402 "Payment Required" y tumbaba el vídeo entero. La miniatura
        # se monta entonces con la primera foto REAL del vídeo y el gancho (como fix_mini.py).
        from PIL import Image
        fotos = sorted((BASE / "cola_imagenes" / vid).glob("img_*.jpg"))
        if not fotos:
            print(f"AVISO: sin miniatura para {vid} ({e}); se usará un fotograma al publicar")
            return None
        print(f"AVISO: miniatura IA no disponible ({str(e)[:80]}); se monta con {fotos[0].name}")
        generar_miniatura.componer(Image.open(fotos[0]), hook, orientacion).save(destino, quality=92)
    print(f"Miniatura lista para la nube: {destino}")
    return destino


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python generar_audio_pipeline.py <config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    audio_final = generar_audio_para_config(cfg)
    generar_imagenes_para_config(cfg)
    generar_subtitulos_para_config(cfg, audio_final)
    generar_miniatura_para_config(cfg)
