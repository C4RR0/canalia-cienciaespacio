import sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\Sergio\CanalIA-CienciaEspacio\scripts")
from qa_imagenes import descargar_commons
from PIL import Image, ImageDraw
out=Path(sys.argv[1]); out.mkdir(exist_ok=True)
ims=[]
for i,t in enumerate(sys.argv[2:]):
    im=descargar_commons(t)
    print(i, t, None if im is None else im.size)
    if im: im.save(out/f"x{i}.jpg",quality=92); ims.append((i,im))
W,H=400,320; hoja=Image.new('RGB',(W*max(1,len(ims)),H),'white'); d=ImageDraw.Draw(hoja)
for k,(i,im) in enumerate(ims):
    th=im.copy(); th.thumbnail((W-6,H-26)); hoja.paste(th,(k*W+3,3)); d.text((k*W+4,H-20),f"x{i}",fill='red')
hoja.save(out/"hoja_x.jpg",quality=80)
