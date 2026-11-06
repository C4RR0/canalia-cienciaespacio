import sys, json
from pathlib import Path
sys.path.insert(0, r"C:\Users\Sergio\CanalIA-CienciaEspacio\scripts")
from qa_imagenes import candidatas_commons, descargar_commons
from PIL import Image, ImageDraw
vid, queries = sys.argv[1], sys.argv[2:]
out = Path(__file__).parent / vid; out.mkdir(exist_ok=True)
vistas=set(); titulos=[]
for q in queries:
    n=candidatas_commons(q, vistas); vistas.update(n); titulos+=n
titulos=titulos[:20]
imgs=[]
for i,t in enumerate(titulos):
    im=descargar_commons(t)
    if im is None: continue
    im.save(out/f"c{i:02d}.jpg", quality=90); imgs.append((i,t,im))
json.dump({f"c{i:02d}":t for i,t,_ in imgs}, open(out/"titulos.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
W,H=320,300; cols=5; rows=(len(imgs)+cols-1)//cols
hoja=Image.new('RGB',(W*cols,H*rows),'white'); d=ImageDraw.Draw(hoja)
for k,(i,t,im) in enumerate(imgs):
    th=im.copy(); th.thumbnail((W-6,H-26)); x=(k%cols)*W; y=(k//cols)*H
    hoja.paste(th,(x+3,y+3)); d.text((x+4,y+H-20),f"c{i:02d}",fill='red')
hoja.save(out/"hoja.jpg",quality=80); print(len(imgs),"candidatas")
