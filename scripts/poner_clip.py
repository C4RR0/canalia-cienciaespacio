"""
QA / mejora visual: sustituye la foto img_NN de un Short en cola por un CLIP
DE VÍDEO REAL de Wikimedia Commons (cola_imagenes/<id>/img_NN.mp4).

Por qué: los dos Shorts que se han disparado (ave lira, avispa zombi) son de
comportamientos que dan ganas de VER, y en el del ave lira la gente se quejó
de solo ver fotos. Un clip real del animal en movimiento vale más que la foto.

Uso:
    python poner_clip.py buscar "<consulta>"            lista vídeos de Commons
    python poner_clip.py poner <id> <n> "File:X.webm" [inicio_s]

El clip se recorta a 12 s desde inicio_s, se pasa a H.264 sin audio (≤1080p)
y se añade el crédito (autor + licencia) a "creditos" del config, que
producir_video.py pega en la descripción (la mayoría de Commons es CC BY/BY-SA
y exige atribución). Revisar SIEMPRE el clip a ojo antes de commitear.
"""
import json
import re
import subprocess
import time
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from ensamblar_video_v2 import resolver_bin

BASE = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
CABECERAS = {"User-Agent": "SabiasQueCanal/1.0 (canal educativo; contacto via YouTube)"}
DUR_CLIP = 12


def buscar(consulta: str):
    r = requests.get(API, headers=CABECERAS, timeout=30, params={
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrlimit": 15, "gsrsearch": f"{consulta} filetype:video",
        "prop": "imageinfo", "iiprop": "size|extmetadata"})
    for p in r.json().get("query", {}).get("pages", {}).values():
        ii = p["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        lic = meta.get("LicenseShortName", {}).get("value", "?")
        print(f"{p['title']}  [{ii.get('width')}x{ii.get('height')}, {float(ii.get('duration', 0)):.0f}s, {lic}]")


def _limpiar_html(txt: str) -> str:
    return re.sub(r"<[^>]+>", "", txt).strip()


def _descargar(titulo: str, url_original: str, destino: Path):
    """El original suele dar 429 (igual que las fotos grandes): se prueba y,
    si falla, se baja la versión transcodificada más alta (≤1080p)."""
    r = requests.get(API, headers=CABECERAS, timeout=30, params={
        "action": "query", "format": "json", "titles": titulo,
        "prop": "videoinfo", "viprop": "derivatives"})
    pagina = next(iter(r.json()["query"]["pages"].values()))
    derivadas = [d for d in pagina["videoinfo"][0].get("derivatives", [])
                 if "/transcoded/" in d["src"] and int(d.get("height", 0)) <= 1080]
    derivadas.sort(key=lambda d: -int(d.get("height", 0)))
    for url in [url_original] + [d["src"] for d in derivadas]:
        for intento in range(2):
            with requests.get(url, headers=CABECERAS, timeout=180, stream=True) as d:
                if d.status_code == 429:
                    time.sleep(8)
                    continue
                d.raise_for_status()
                with open(destino, "wb") as f:
                    for trozo in d.iter_content(1 << 20):
                        f.write(trozo)
                print(f"Descargado: {url}")
                return
    raise SystemExit("Commons da 429 en todas las versiones: reintentar más tarde")


def poner(vid: str, n: int, titulo: str, inicio: float):
    r = requests.get(API, headers=CABECERAS, timeout=30, params={
        "action": "query", "format": "json", "titles": titulo,
        "prop": "imageinfo", "iiprop": "url|extmetadata"})
    pagina = next(iter(r.json()["query"]["pages"].values()))
    ii = pagina["imageinfo"][0]
    meta = ii.get("extmetadata", {})
    autor = _limpiar_html(meta.get("Artist", {}).get("value", "desconocido"))
    licencia = meta.get("LicenseShortName", {}).get("value", "")
    if not any(x in licencia.lower() for x in ("cc", "public domain", "pd")):
        raise SystemExit(f"Licencia no reconocida ({licencia}): no se usa")

    carpeta = BASE / "cola_imagenes" / vid
    tmp = carpeta / f"_descarga_{n:02d}"
    _descargar(titulo, ii["url"], tmp)

    ffmpeg, _ = resolver_bin()
    salida = carpeta / f"img_{n:02d}.mp4"
    subprocess.run([ffmpeg, "-y", "-ss", str(inicio), "-i", str(tmp), "-t", str(DUR_CLIP), "-an",
                    "-vf", "scale=-2:'min(1080,ih)'", "-c:v", "libx264", "-crf", "20",
                    "-pix_fmt", "yuv420p", str(salida)], check=True, capture_output=True)
    tmp.unlink()
    foto = carpeta / f"img_{n:02d}.jpg"
    if foto.exists():
        foto.unlink()

    cfg_path = BASE / "produccion_config" / f"{vid}.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    credito = f"Vídeo: {titulo.removeprefix('File:')}, de {autor} ({licencia}), vía Wikimedia Commons"
    creditos = [c for c in cfg.get("creditos", []) if titulo.removeprefix("File:") not in c]
    cfg["creditos"] = creditos + [credito]
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{salida} ({credito})")


if __name__ == "__main__":
    if sys.argv[1] == "buscar":
        buscar(sys.argv[2])
    else:
        poner(sys.argv[2], int(sys.argv[3]), sys.argv[4], float(sys.argv[5]) if len(sys.argv) > 5 else 0)
