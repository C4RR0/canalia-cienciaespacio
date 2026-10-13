"""
QA visual AUTOMÁTICA de las imágenes de un Short (sin Claude ni PC), con
Gemini gratis (ver gemini.py). Hace lo que hasta el 13/10/2026 hacía Claude a
mano mirando hojas de contactos:

1. Juzga cada cola_imagenes/<id>/img_NN.jpg: ¿es una FOTO real del tema del
   vídeo? Rechaza mapas, gráficas, texto, imágenes IA raras, otra especie u
   otro lugar con el mismo nombre, fotos borrosas y duplicados.
2. Sustituye las malas (y rellena los huecos hasta 8) con candidatas de
   Wikimedia Commons, que también pasan por el juicio de Gemini.
3. Compone la miniatura con la mejor foto (generar_miniatura.componer).

Uso:
    python qa_imagenes.py <id> [<id> ...]

Errores típicos que motivan cada regla: ver aprendizajes.md (26/09, 29/09,
05/10, 07/10 y 13/10).
"""
import json
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import gemini
import generar_miniatura

BASE = Path(__file__).resolve().parent.parent
COMMONS = "https://commons.wikimedia.org/w/api.php"
H = {"User-Agent": "SabiasQueCanal/1.0 (educational YouTube shorts)"}
N_IMAGENES = 8
PAUSA = 4  # segundos entre llamadas: el plan gratis limita peticiones por minuto

SISTEMA = """Revisas fotos para un vídeo corto de divulgación (YouTube Shorts) sobre un tema \
concreto. Cada foto se verá unos segundos a pantalla completa mientras la voz habla del tema.

Una foto es APTA solo si:
- Es una fotografía real (o una foto histórica / ilustración de época si el tema es histórico).
- Muestra claramente el sujeto del vídeo (la especie, el lugar, el objeto o el suceso), o algo \
directamente relacionado que se menciona en el guion.
- Se entiende sin leer: NO mapas, gráficas, diagramas, esquemas, tablas, documentos, sellos, \
carteles con mucho texto, ni láminas científicas con letras o escalas.
- No parece generada por IA (rasgos deformes, anatomía imposible, aspecto de dibujo o 3D).
- No es otra cosa con el mismo nombre (otra especie, otro pueblo, una persona homónima, un \
producto comercial, un logotipo).
- No está muy borrosa, minúscula o casi toda vacía.

Además puntúa de 0 a 10 lo buena que sería como MINIATURA: impactante, sujeto grande y \
reconocible, sin texto."""

ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "apta": {"type": "BOOLEAN"},
        "motivo": {"type": "STRING"},
        "miniatura": {"type": "INTEGER"},
    },
    "required": ["apta", "motivo", "miniatura"],
}


def huella(img: Image.Image) -> int:
    """Hash medio de 8x8: detecta la misma foto a otra resolución o recorte leve."""
    g = img.convert("L").resize((8, 8))
    px = list(g.getdata())
    media = sum(px) / 64
    return sum(1 << i for i, p in enumerate(px) if p > media)


def parecidas(a: int, b: int) -> bool:
    return bin(a ^ b).count("1") <= 6


def juzgar(img: Image.Image, cfg: dict) -> dict:
    tema = (f"Título: {cfg['titulo']}\nDescripción: {cfg.get('descripcion', '').split(chr(10))[0]}\n"
            f"Guion: {cfg.get('guion', '')}")
    time.sleep(PAUSA)
    r = gemini.json_estructurado(SISTEMA, [{"text": tema}, gemini.parte_imagen(img)], ESQUEMA)
    return r or {"apta": False, "motivo": "sin respuesta", "miniatura": 0}


def candidatas_commons(query: str, vistas: set) -> list[str]:
    """Títulos de ficheros de Commons para la búsqueda (solo imágenes de mapa de bits)."""
    try:
        r = requests.get(COMMONS, headers=H, timeout=30, params={
            "action": "query", "format": "json", "list": "search", "srnamespace": 6,
            "srsearch": f"{query} filetype:bitmap", "srlimit": 8}).json()
    except (requests.RequestException, ValueError):
        return []
    return [s["title"] for s in r.get("query", {}).get("search", []) if s["title"] not in vistas]


def descargar_commons(titulo: str) -> Image.Image | None:
    """Miniatura de 1280 px (las originales grandes dan 429); reintenta con espera."""
    try:
        r = requests.get(COMMONS, headers=H, timeout=30, params={
            "action": "query", "format": "json", "titles": titulo,
            "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 1280}).json()
        info = next(iter(r["query"]["pages"].values()))["imageinfo"][0]
    except (requests.RequestException, ValueError, KeyError, StopIteration):
        return None
    for intento in range(4):
        try:
            resp = requests.get(info.get("thumburl") or info["url"], headers=H, timeout=60)
        except requests.RequestException:
            resp = None
        if resp is not None and resp.status_code == 200:
            try:
                img = Image.open(BytesIO(resp.content)).convert("RGB")
            except Exception:
                return None
            ancho, alto = img.size
            # Panorámicas muy estrechas se ven fatal en vertical
            if min(ancho, alto) < 300 or max(ancho, alto) / min(ancho, alto) > 2.6:
                return None
            return img
        time.sleep(15 * (intento + 1))
    return None


def revisar(vid: str):
    cfg = json.loads((BASE / "produccion_config" / f"{vid}.json").read_text(encoding="utf-8"))
    carpeta = BASE / "cola_imagenes" / vid
    print(f"\n=== QA {vid}: {cfg['titulo']}")

    buenas = {}  # n -> (huella, nota miniatura)
    malas = []
    for n in range(1, N_IMAGENES + 1):
        f = carpeta / f"img_{n:02d}.jpg"
        if not f.exists():
            malas.append(n)
            print(f"  img_{n:02d}: falta")
            continue
        img = Image.open(f)
        h = huella(img)
        if any(parecidas(h, b[0]) for b in buenas.values()):
            malas.append(n)
            print(f"  img_{n:02d}: duplicada")
            continue
        j = juzgar(img, cfg)
        print(f"  img_{n:02d}: {'OK ' if j['apta'] else 'MAL'} ({j['miniatura']}) {j['motivo'][:90]}")
        if j["apta"]:
            buenas[n] = (h, j["miniatura"])
        else:
            malas.append(n)

    # Búsquedas para sustituir: las del config y variantes con el título de Commons
    vistas = set()
    queries = list(dict.fromkeys(cfg.get("queries_imagenes", [])))
    pendientes_q = []
    for q in queries:
        pendientes_q.extend(candidatas_commons(q, vistas))
        vistas.update(pendientes_q)
        if len(pendientes_q) >= 4 * max(len(malas), 1) + 8:
            break
    for n in malas:
        puesta = False
        while pendientes_q and not puesta:
            titulo = pendientes_q.pop(0)
            img = descargar_commons(titulo)
            if img is None:
                continue
            h = huella(img)
            if any(parecidas(h, b[0]) for b in buenas.values()):
                continue
            j = juzgar(img, cfg)
            if j["apta"]:
                img.save(carpeta / f"img_{n:02d}.jpg", quality=92)
                buenas[n] = (h, j["miniatura"])
                puesta = True
                print(f"  img_{n:02d} <- {titulo} ({j['miniatura']})")
        if not puesta:
            print(f"  img_{n:02d}: sin sustituta apta")

    # Si quedan huecos, se rellenan copiando las buenas (el montaje necesita 8 seguidas)
    numeros = sorted(buenas)
    if not numeros:
        raise RuntimeError(f"{vid}: ninguna imagen apta, revisar a mano")
    for i, n in enumerate(n for n in range(1, N_IMAGENES + 1) if n not in buenas):
        origen = numeros[i % len(numeros)]
        (carpeta / f"img_{n:02d}.jpg").write_bytes((carpeta / f"img_{origen:02d}.jpg").read_bytes())
        print(f"  img_{n:02d}: copia de img_{origen:02d} (no hubo sustituta)")
    (carpeta / "_reales.json").write_text(json.dumps([True] * N_IMAGENES))

    mejor = max(buenas, key=lambda n: buenas[n][1])
    mini = generar_miniatura.componer(Image.open(carpeta / f"img_{mejor:02d}.jpg"),
                                      cfg["hook_miniatura"], cfg.get("orientacion", "vertical"))
    (BASE / "cola_miniaturas").mkdir(exist_ok=True)
    mini.save(BASE / "cola_miniaturas" / f"{vid}.jpg", quality=92)
    print(f"  miniatura con img_{mejor:02d}; {len(buenas)}/{N_IMAGENES} aptas")
    return len(buenas)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    fallos = 0
    for vid in sys.argv[1:]:
        try:
            revisar(vid)
        except Exception as e:
            print(f"FALLO QA {vid}: {e}")
            fallos += 1
    sys.exit(1 if fallos else 0)
