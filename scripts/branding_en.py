"""
Logo, banner y marca de agua de Wild Facts Daily (15/10/2026). Amarillo y negro,
los mismos colores que el gancho y la marca de los Shorts, para que vídeo y canal
se reconozcan como una sola cosa.

Uso:
    python scripts/branding_en.py        -> branding/en_logo.png, en_banner.png, en_marca_agua.png
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent.parent
SALIDA = BASE / "branding"
AMARILLO = (255, 212, 0)
NEGRO = (12, 12, 12)
BLANCO = (245, 245, 245)
FUENTES = [r"C:\Windows\Fonts\ariblk.ttf", "/usr/share/fonts/truetype/msttcorefonts/Arial_Black.ttf",
           r"C:\Windows\Fonts\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def fuente(tamano):
    for ruta in FUENTES:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def texto_centrado(d, cx, cy, texto, f, relleno, **kw):
    x0, y0, x1, y1 = d.textbbox((0, 0), texto, font=f, stroke_width=kw.get("stroke_width", 0))
    d.text((cx - (x1 - x0) / 2 - x0, cy - (y1 - y0) / 2 - y0), texto, font=f, fill=relleno, **kw)


def fondo_rayas(ancho, alto, semilla=7):
    """Negro con zarpazos diagonales amarillos muy tenues (textura salvaje, sin fotos)."""
    img = Image.new("RGB", (ancho, alto), NEGRO)
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    rnd = random.Random(semilla)
    for _ in range(int(ancho * alto / 60000)):
        x, y = rnd.uniform(-200, ancho), rnd.uniform(-200, alto)
        largo, ang = rnd.uniform(120, 420), math.radians(rnd.uniform(-60, -30))
        for k in range(3):  # tres garras paralelas
            dx, dy = k * 26, k * 10
            d.line([(x + dx, y + dy), (x + dx + largo * math.cos(ang), y + dy + largo * math.sin(ang))],
                   fill=AMARILLO + (rnd.randint(10, 26),), width=rnd.randint(6, 12))
    capa = capa.filter(ImageFilter.GaussianBlur(1.5))
    img.paste(capa, (0, 0), capa)
    # viñeta
    vin = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(vin).ellipse([-ancho * 0.2, -alto * 0.4, ancho * 1.2, alto * 1.4], fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(min(ancho, alto) / 5))
    return Image.composite(img, Image.new("RGB", (ancho, alto), (0, 0, 0)), vin)


def logo(lado=1024):
    img = fondo_rayas(lado, lado, semilla=3)
    d = ImageDraw.Draw(img)
    m = lado * 0.07
    d.ellipse([m, m, lado - m, lado - m], fill=AMARILLO)
    d.ellipse([m + lado * 0.035] * 2 + [lado - m - lado * 0.035] * 2, outline=NEGRO, width=int(lado * 0.012))
    texto_centrado(d, lado / 2, lado * 0.40, "WILD", fuente(int(lado * 0.205)), NEGRO)
    texto_centrado(d, lado / 2, lado * 0.62, "FACTS", fuente(int(lado * 0.165)), NEGRO)
    texto_centrado(d, lado / 2, lado * 0.775, "DAILY", fuente(int(lado * 0.075)), NEGRO)
    return img


def banner(ancho=2560, alto=1440):
    img = fondo_rayas(ancho, alto)
    d = ImageDraw.Draw(img)
    cx, cy = ancho / 2, alto / 2  # zona segura: 1546x423 centrada
    texto_centrado(d, cx, cy - 70, "WILD FACTS DAILY", fuente(150), AMARILLO,
                   stroke_width=6, stroke_fill=NEGRO)
    texto_centrado(d, cx, cy + 50, "BRUTAL ANIMALS  •  FORBIDDEN PLACES  •  TRUE STORIES",
                   fuente(44), BLANCO)
    f = fuente(40)
    t = "A NEW WILD FACT EVERY DAY"
    x0, y0, x1, y1 = d.textbbox((0, 0), t, font=f)
    w, h = x1 - x0 + 70, y1 - y0 + 34
    d.rounded_rectangle([cx - w / 2, cy + 120, cx + w / 2, cy + 120 + h], radius=h / 2, fill=AMARILLO)
    texto_centrado(d, cx, cy + 120 + h / 2, t, f, NEGRO)
    return img


if __name__ == "__main__":
    SALIDA.mkdir(exist_ok=True)
    logo().save(SALIDA / "en_logo.png")
    banner().save(SALIDA / "en_banner.png", optimize=True)
    logo(300).resize((150, 150), Image.LANCZOS).save(SALIDA / "en_marca_agua.png")
    print("Hecho:", ", ".join(p.name for p in SALIDA.glob("en_*.png")))
