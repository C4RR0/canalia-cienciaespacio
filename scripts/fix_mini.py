"""
QA visual: rehace la miniatura de <id> componiéndola con una foto REAL de su
cola de imágenes (cuando la miniatura IA no representa el tema).

Uso:
    python scripts/fix_mini.py <id> <n>
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import generar_miniatura

BASE = Path(__file__).resolve().parent.parent

vid, n = sys.argv[1], int(sys.argv[2])
cfg = json.loads((BASE / "produccion_config" / f"{vid}.json").read_text(encoding="utf-8"))
img = Image.open(BASE / "cola_imagenes" / vid / f"img_{n:02d}.jpg")
mini = generar_miniatura.componer(img, cfg["hook_miniatura"], cfg.get("orientacion", "vertical"))
salida = BASE / "cola_miniaturas" / f"{vid}.jpg"
mini.save(salida, quality=92)
print(f"Miniatura rehecha con img_{n:02d}: {salida}")
