"""
QA visual: sustituye una imagen de cola_imagenes/<id>/img_NN.jpg por la
primera foto de Wikimedia que encuentre para otra búsqueda, y actualiza la
query en el config y _reales.json.

Uso:
    python scripts/fix_img.py <id> <n> "<query>"
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import buscar_imagenes_wikimedia as wm

BASE = Path(__file__).resolve().parent.parent

vid, n, query = sys.argv[1], int(sys.argv[2]), sys.argv[3]
destino = BASE / "cola_imagenes" / vid / f"img_{n:02d}.jpg"
# Huellas de las demás imágenes del vídeo, para no meter una foto repetida.
huellas = {hashlib.md5(p.read_bytes()).hexdigest()
           for p in destino.parent.glob("img_*.jpg") if p != destino}
probadas = set()
while True:
    url = wm.buscar_archivo(query, excluir=probadas)
    if not url:
        sys.exit(f"Sin resultados relevantes (y no repetidos) para '{query}'")
    tmp = destino.with_suffix(".tmp.jpg")
    wm.descargar(url, tmp)
    if hashlib.md5(tmp.read_bytes()).hexdigest() not in huellas:
        tmp.replace(destino)
        break
    tmp.unlink()
    print(f"  repetida, se prueba otra: {url[:90]}")
print(f"img_{n:02d} <- {url}")

cfg_path = BASE / "produccion_config" / f"{vid}.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
cfg["queries_imagenes"][n - 1] = query
cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

reales_path = destino.parent / "_reales.json"
reales = json.loads(reales_path.read_text())
reales[n - 1] = True
reales_path.write_text(json.dumps(reales))
