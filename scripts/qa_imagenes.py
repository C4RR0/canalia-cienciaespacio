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
MIN_APTAS = 5  # con menos, el vídeo repetiría demasiado las mismas fotos: a mano
PAUSA = 4  # segundos entre llamadas: el plan gratis limita peticiones por minuto
# Las fotos se juzgan en lotes (una llamada por lote): una a una, 5 vídeos
# tardaban más de 90 min por los límites por minuto del plan gratis (13/10).

SISTEMA = """Revisas fotos para un vídeo corto de divulgación (YouTube Shorts) sobre un tema \
concreto. Cada foto se verá unos segundos a pantalla completa mientras la voz habla del tema.

Una foto es APTA solo si:
- Es una fotografía real (o una foto histórica / ilustración de época si el tema es histórico).
- Muestra claramente el sujeto del vídeo (la especie, el lugar, el objeto o el suceso), o algo \
directamente relacionado que se menciona en el guion.
- Se entiende sin leer: NO mapas, gráficas, diagramas, esquemas, tablas, documentos, sellos, \
carteles con mucho texto, ni láminas científicas con letras o escalas.
- No parece generada por IA (rasgos deformes, anatomía imposible, aspecto de dibujo o 3D, \
animales o crías demasiado perfectos y esponjosos, como de peluche). Si dudas, NO es apta.
- No es otra cosa con el mismo nombre (otra especie, otro pueblo, una persona homónima, un \
producto comercial, un logotipo).
- No está muy borrosa, minúscula o casi toda vacía.

Además puntúa de 0 a 10 lo buena que sería como MINIATURA: impactante, sujeto grande y \
reconocible, sin texto."""

ESQUEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "n": {"type": "INTEGER"},
            "apta": {"type": "BOOLEAN"},
            "motivo": {"type": "STRING"},
            "miniatura": {"type": "INTEGER"},
        },
        "required": ["n", "apta", "motivo", "miniatura"],
    },
}


def huella(img: Image.Image) -> int:
    """Hash medio de 8x8: detecta la misma foto a otra resolución o recorte leve."""
    g = img.convert("L").resize((8, 8))
    px = list(g.tobytes())
    media = sum(px) / 64
    return sum(1 << i for i, p in enumerate(px) if p > media)


def parecidas(a: int, b: int) -> bool:
    return bin(a ^ b).count("1") <= 6


def _un_juicio(imgs: list, cfg: dict) -> list[dict]:
    tema = (f"Título: {cfg['titulo']}\nDescripción: {cfg.get('descripcion', '').split(chr(10))[0]}\n"
            f"Guion: {cfg.get('guion', '')}")
    partes = [{"text": tema}]
    for i, img in enumerate(imgs, 1):
        partes += [{"text": f"Foto {i}:"}, gemini.parte_imagen(img, 640)]
    time.sleep(PAUSA)
    r = gemini.json_estructurado(SISTEMA, partes, ESQUEMA) or []
    por_n = {v.get("n"): v for v in r if isinstance(v, dict)}
    return [por_n.get(i, {"apta": False, "motivo": "sin respuesta", "miniatura": 0})
            for i in range(1, len(imgs) + 1)]


def juzgar(imgs: list, cfg: dict) -> list[dict]:
    """Un veredicto por imagen, en el mismo orden. Se juzga dos veces (la
    segunda en orden inverso) y solo es apta si lo es en las dos: un solo
    juicio dio por buena una cría hecha con IA que en otra pasada rechazó (13/10)."""
    if not imgs:
        return []
    a = _un_juicio(imgs, cfg)
    b = _un_juicio(imgs[::-1], cfg)[::-1]
    return [x if not x["apta"] else y if not y["apta"]
            else {**x, "miniatura": min(x["miniatura"], y["miniatura"])}
            for x, y in zip(a, b)]


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
    a_juzgar = []  # (n, imagen, huella)
    for n in range(1, N_IMAGENES + 1):
        f = carpeta / f"img_{n:02d}.jpg"
        if not f.exists():
            malas.append(n)
            print(f"  img_{n:02d}: falta")
            continue
        img = Image.open(f).convert("RGB")
        h = huella(img)
        if any(parecidas(h, x[2]) for x in a_juzgar):
            malas.append(n)
            print(f"  img_{n:02d}: duplicada")
            continue
        a_juzgar.append((n, img, h))
    for (n, _, h), j in zip(a_juzgar, juzgar([x[1] for x in a_juzgar], cfg)):
        print(f"  img_{n:02d}: {'OK ' if j['apta'] else 'MAL'} ({j['miniatura']}) {j['motivo'][:90]}")
        if j["apta"]:
            buenas[n] = (h, j["miniatura"])
        else:
            malas.append(n)
    malas.sort()

    # Sustitutas de Commons con las búsquedas del config, juzgadas por lotes
    vistas = set()
    titulos = []
    for q in dict.fromkeys(cfg.get("queries_imagenes", [])):
        nuevos = candidatas_commons(q, vistas)
        vistas.update(nuevos)
        titulos.extend(nuevos)
        if len(titulos) >= 3 * len(malas) + 6:
            break
    for _ in range(3):
        if not malas or not titulos:
            break
        lote = []  # (titulo, imagen, huella)
        while titulos and len(lote) < min(10, len(malas) + 4):
            titulo = titulos.pop(0)
            img = descargar_commons(titulo)
            if img is None:
                continue
            h = huella(img)
            if any(parecidas(h, b[0]) for b in buenas.values()) or any(parecidas(h, x[2]) for x in lote):
                continue
            lote.append((titulo, img, h))
        veredictos = juzgar([x[1] for x in lote], cfg)
        aptas = sorted((v["miniatura"], i) for i, v in enumerate(veredictos) if v["apta"])[::-1]
        for nota, i in aptas:
            if not malas:
                break
            titulo, img, h = lote[i]
            n = malas.pop(0)
            img.save(carpeta / f"img_{n:02d}.jpg", quality=92)
            buenas[n] = (h, nota)
            print(f"  img_{n:02d} <- {titulo} ({nota})")
    for n in malas:
        print(f"  img_{n:02d}: sin sustituta apta")

    # Si quedan huecos, se rellenan copiando las buenas (el montaje necesita 8 seguidas)
    numeros = sorted(buenas)
    if len(numeros) < MIN_APTAS:
        # 13/10: short_160 quedó con 1/8 y se dio por bueno rellenando con copias
        raise RuntimeError(f"{vid}: solo {len(numeros)}/{N_IMAGENES} aptas, revisar a mano")
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
