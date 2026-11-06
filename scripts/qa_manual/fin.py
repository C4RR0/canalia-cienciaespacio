import sys, json, shutil
from pathlib import Path
from PIL import Image
sys.path.insert(0, r"C:\Users\Sergio\CanalIA-CienciaEspacio\scripts")
import generar_miniatura
BASE=Path(r"C:\Users\Sergio\CanalIA-CienciaEspacio")
vid=sys.argv[1]; fuentes=[Path(p) for p in sys.argv[2:]]
cfg=json.loads((BASE/"produccion_config"/f"{vid}.json").read_text(encoding="utf-8"))
carpeta=BASE/"cola_imagenes"/vid
datos=[Image.open(f).convert("RGB") for f in fuentes]
for n in range(1,9):
    datos[(n-1)%len(datos)].save(carpeta/f"img_{n:02d}.jpg",quality=92)
(carpeta/"_reales.json").write_text(json.dumps([True]*8))
mini=generar_miniatura.componer(datos[0].copy(), cfg["hook_miniatura"], cfg.get("orientacion","vertical"))
mini.save(BASE/"cola_miniaturas"/f"{vid}.jpg",quality=92)
p=BASE/"pendientes_qa.txt"
lin=[l for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and l.strip()!=vid]
p.write_text("\n".join(lin)+("\n" if lin else ""),encoding="utf-8")
print(vid,"OK con",len(datos),"fotos; miniatura con",fuentes[0].name)
