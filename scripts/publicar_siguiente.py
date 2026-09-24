"""
Publica el SIGUIENTE vídeo listo de la cola (uno solo por ejecución).

Sustituye a la rutina de Claude en la nube: la lógica es 100% determinista,
así que no necesita IA. Lo usa el workflow de GitHub Actions
(.github/workflows/publicar.yml) y también sirve para ponerse al día en local.

Un <id> está listo si existen:
    cola_audio/<id>_final.mp3
    cola_imagenes/<id>/ (con imágenes)
    cola_subtitulos/<id>_corregido.srt
    produccion_config/<id>.json
(.ass, miniatura y clips IA son opcionales).

Tras publicar con éxito borra los ficheros de cola de ese <id>; el commit/push
lo hace quien llama (workflow o persona en local).

Uso:
    python scripts/publicar_siguiente.py            # publica 1
    python scripts/publicar_siguiente.py --listar   # solo lista los listos

Salida: código 0 si publicó o no había nada; 1 si falló la producción/subida.
Escribe la línea "PUBLICADO=<id>" para que el workflow la use en el commit.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# Script productor de cada canal (el primero que exista).
PRODUCTORES = ["scripts/producir_video.py", "scripts/producir_mito.py"]


def ids_listos() -> list[str]:
    listos = []
    for audio in sorted((BASE / "cola_audio").glob("*_final.mp3")):
        vid = audio.name[: -len("_final.mp3")]
        imgs = BASE / "cola_imagenes" / vid
        if (imgs.is_dir() and any(imgs.iterdir())
                and (BASE / "cola_subtitulos" / f"{vid}_corregido.srt").exists()
                and (BASE / "produccion_config" / f"{vid}.json").exists()):
            listos.append(vid)
    return listos


def limpiar_cola(vid: str):
    for f in [BASE / "cola_audio" / f"{vid}_final.mp3",
              BASE / "cola_subtitulos" / f"{vid}_corregido.srt",
              BASE / "cola_subtitulos" / f"{vid}_corregido.ass",
              BASE / "cola_miniaturas" / f"{vid}.jpg"]:
        f.unlink(missing_ok=True)
    for d in [BASE / "cola_imagenes" / vid, BASE / "cola_clips_ia" / vid]:
        if d.exists():
            shutil.rmtree(d)


def main():
    listos = ids_listos()
    print(f"Listos en cola: {len(listos)} {listos}")
    if "--listar" in sys.argv or not listos:
        if not listos:
            print("Nada pendiente en la cola.")
        return 0

    vid = listos[0]
    productor = next(BASE / p for p in PRODUCTORES if (BASE / p).exists())
    config = BASE / "produccion_config" / f"{vid}.json"
    print(f"Produciendo {vid} con {productor.name}...", flush=True)
    subprocess.run([sys.executable, str(productor), str(config)], cwd=BASE)

    resultado_path = BASE / "salidas" / f"resultado_{vid}.json"
    resultado = json.loads(resultado_path.read_text(encoding="utf-8")) if resultado_path.exists() else {}
    if not resultado.get("video_id"):
        print(f"ERROR: {vid} no se publicó: {resultado.get('error_subida') or 'sin resultado'}")
        return 1

    limpiar_cola(vid)
    print(f"Publicado: {resultado['video_url']}  (quedan {len(listos) - 1} en cola)")
    print(f"PUBLICADO={vid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
