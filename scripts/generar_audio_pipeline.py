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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python generar_audio_pipeline.py <config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    generar_audio_para_config(cfg)
    generar_imagenes_para_config(cfg)
