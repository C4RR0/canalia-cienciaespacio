"""
Versión en inglés de un Short para el canal en inglés (15/10/2026).

Se llama justo después de publicar el Short en español y ANTES de limpiar la
cola, para reutilizar sus imágenes. Traduce con Gemini (gratis) guion, título,
descripción, tags y gancho; genera voz en inglés, subtítulos con la marca
"DID YOU KNOW?" y lo sube con token_en.json.

Si falta token_en.json no hace nada. Nunca debe tumbar la publicación en
español: quien lo llama ignora su código de salida.

Uso:
    python scripts/publicar_ingles.py <id>            # traduce, renderiza y sube
    python scripts/publicar_ingles.py <id> --prueba   # solo renderiza (no hace falta token)
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gemini  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
TOKEN_EN = "token_en.json"
VOZ_EN = "en-US-AndrewNeural"

SISTEMA = (
    "You adapt Spanish YouTube Shorts about amazing animals, places and true stories into "
    "natural, punchy American English for a US audience. Keep every fact EXACTLY as in the "
    "original: do not add, remove or exaggerate facts, numbers or names. The script is read "
    "aloud by a narrator: short sentences separated by a blank line, a first sentence that "
    "hooks in one second, numbers written as words when short, no stage directions, roughly "
    "the same length as the original (never longer). Keep the narrator's personal opinion "
    "line if there is one. Any line inviting viewers to follow 'Sabías Qué' must invite them "
    "to follow this channel instead, without naming it. The title must not reveal the "
    "animal, place or person if the original does not; 40-60 characters, no quotes or "
    "parentheses. The hook is 2-5 words in CAPITALS that do not reveal the subject. The "
    "description: 1-2 sentences naming the real subject and the fact, a blank line, then 3 "
    "English hashtags and #shorts. Tags: 5-7 English tags, the first one the subject's name."
)
ESQUEMA = {"type": "OBJECT", "properties": {
    "titulo": {"type": "STRING"}, "guion": {"type": "STRING"}, "descripcion": {"type": "STRING"},
    "hook": {"type": "STRING"}, "tags": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["titulo", "guion", "descripcion", "hook", "tags"]}


def traducir(cfg: dict) -> dict:
    texto = (f"TITLE:\n{cfg['titulo']}\n\nSCRIPT:\n{cfg['guion']}\n\n"
             f"DESCRIPTION:\n{cfg['descripcion']}\n\nHOOK:\n{cfg.get('hook_miniatura', '')}\n\n"
             f"TAGS:\n{', '.join(cfg.get('tags', []))}")
    t = gemini.json_estructurado(SISTEMA, [{"text": texto}], ESQUEMA)
    if not t or len(t["guion"].split()) < 40:
        raise RuntimeError(f"Traducción vacía o demasiado corta: {t}")
    largo_es, largo_en = len(cfg["guion"].split()), len(t["guion"].split())
    if largo_en > largo_es * 1.25:
        raise RuntimeError(f"Guion en inglés demasiado largo ({largo_en} palabras vs {largo_es})")
    return t


def main(vid: str, prueba: bool = False) -> int:
    if not prueba and not (BASE / TOKEN_EN).exists():
        print("Sin token_en.json: no hay canal en inglés configurado, nada que hacer.")
        return 0
    cfg = json.loads((BASE / "produccion_config" / f"{vid}.json").read_text(encoding="utf-8"))
    if cfg.get("formato") != "curiosidad":
        print(f"{vid}: formato {cfg.get('formato')}, solo se traducen Shorts de curiosidad.")
        return 0

    t = traducir(cfg)
    vid_en = f"{vid}_en"
    cfg_en = dict(cfg, id=vid_en, idioma="en", voz=VOZ_EN, marca="DID YOU KNOW?",
                  titulo=t["titulo"].strip(), guion=t["guion"].strip(),
                  descripcion=t["descripcion"].strip(), hook_miniatura=t["hook"].strip(),
                  tags=[x.strip() for x in t["tags"]][:7], categoria_id=cfg.get("categoria_id", "28"))
    cfg_en.pop("correcciones_subtitulos", None)
    cfg_en.pop("solo_render", None)
    if prueba:
        cfg_en["solo_render"] = True
    print(f"EN: {cfg_en['titulo']}\n{cfg_en['guion']}\n")

    # Mismas imágenes y clips que la versión en español (aún en la cola).
    origen = BASE / "cola_imagenes" / vid
    destino = BASE / "cola_imagenes" / vid_en
    if destino.exists():
        shutil.rmtree(destino)
    shutil.copytree(origen, destino)

    ruta_cfg = BASE / "salidas" / f"_cfg_{vid_en}.json"
    ruta_cfg.parent.mkdir(exist_ok=True)
    ruta_cfg.write_text(json.dumps(cfg_en, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        subprocess.run([sys.executable, str(BASE / "scripts" / "producir_video.py"), str(ruta_cfg)],
                       cwd=BASE, check=True, env=dict(os.environ, YOUTUBE_TOKEN_FILE=TOKEN_EN))
    finally:
        shutil.rmtree(destino, ignore_errors=True)

    if prueba:
        final = BASE / "salidas" / f"{vid_en}_FINAL.mp4"
        print(f"PRUEBA_EN {'OK' if final.exists() else 'FALLIDA'}: {final}")
        return 0 if final.exists() else 1
    resultado = json.loads((BASE / "salidas" / f"resultado_{vid_en}.json").read_text(encoding="utf-8"))
    if not resultado.get("video_id"):
        print(f"ERROR EN: {resultado.get('error_subida') or 'sin vídeo'}")
        return 1
    print(f"PUBLICADO_EN={resultado['video_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], "--prueba" in sys.argv))
