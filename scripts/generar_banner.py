"""
Genera el banner del canal (2048x1152), con el mismo estilo visual que el logo:
degradado radial magenta/morado, nombre del canal y eslogan centrados en la zona segura.

Uso:
    python generar_banner.py salida.png "NOMBRE" "eslogan"
"""
import sys
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ANCHO, ALTO = 2048, 1152

NUCLEO = (255, 90, 150)
MEDIO = (124, 40, 180)
BORDE = (10, 4, 24)

FUENTES_BOLD = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]
FUENTES_REGULAR = [
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def cargar_fuente(lista, tamano):
    for ruta in lista:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def generar_fondo_radial(ancho, alto, centro_rel=(0.5, 0.45)):
    fondo = Image.new("RGB", (ancho, alto))
    px = fondo.load()
    cx, cy = ancho * centro_rel[0], alto * centro_rel[1]
    max_dist = math.hypot(max(cx, ancho - cx), max(cy, alto - cy))
    for y in range(alto):
        for x in range(ancho):
            d = math.hypot(x - cx, y - cy) / max_dist
            if d < 0.5:
                color = lerp_color(NUCLEO, MEDIO, d / 0.5)
            else:
                color = lerp_color(MEDIO, BORDE, min((d - 0.5) / 0.5, 1.0))
            px[x, y] = color
    return fondo


def dibujar_estrella(draw, cx, cy, r_ext, r_int, puntas, color):
    puntos = []
    for i in range(puntas * 2):
        ang = math.pi / puntas * i - math.pi / 2
        r = r_ext if i % 2 == 0 else r_int
        puntos.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(puntos, fill=color)


def generar_banner(salida: str, nombre: str, eslogan: str):
    fondo = generar_fondo_radial(ANCHO, ALTO)
    img = fondo.convert("RGBA")
    draw = ImageDraw.Draw(img)

    fuente_nombre = cargar_fuente(FUENTES_BOLD, 150)
    fuente_eslogan = cargar_fuente(FUENTES_REGULAR, 46)

    bbox_n = draw.textbbox((0, 0), nombre, font=fuente_nombre)
    an = bbox_n[2] - bbox_n[0]
    al = bbox_n[3] - bbox_n[1]
    xn = (ANCHO - an) / 2 - bbox_n[0]
    yn = ALTO * 0.46 - al / 2 - bbox_n[1]

    bbox_e = draw.textbbox((0, 0), eslogan, font=fuente_eslogan)
    ae = bbox_e[2] - bbox_e[0]
    xe = (ANCHO - ae) / 2 - bbox_e[0]
    ye = yn + al + 40

    # glow detrás del nombre
    capa_glow = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    dg = ImageDraw.Draw(capa_glow)
    dg.text((xn, yn), nombre, font=fuente_nombre, fill=(255, 235, 160, 255))
    capa_glow = capa_glow.filter(ImageFilter.GaussianBlur(22))
    img = Image.alpha_composite(img, capa_glow)

    draw = ImageDraw.Draw(img)
    # sombra sutil
    draw.text((xn + 4, yn + 6), nombre, font=fuente_nombre, fill=(0, 0, 0, 140))
    draw.text((xn, yn), nombre, font=fuente_nombre, fill=(255, 250, 235, 255))

    draw.text((xe + 2, ye + 3), eslogan, font=fuente_eslogan, fill=(0, 0, 0, 120))
    draw.text((xe, ye), eslogan, font=fuente_eslogan, fill=(240, 225, 255, 255))

    # destellos decorativos dentro de zona segura pero fuera del texto
    dibujar_estrella(draw, ANCHO * 0.5 - an / 2 - 70, yn + al * 0.3, 26, 11, 4, (255, 255, 255, 230))
    dibujar_estrella(draw, ANCHO * 0.5 + an / 2 + 70, yn + al * 0.15, 34, 14, 4, (255, 255, 255, 230))

    img.convert("RGB").save(salida, quality=95)
    print(f"Banner generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print('Uso: python generar_banner.py <salida.png> "<nombre>" "<eslogan>"')
        sys.exit(1)

    generar_banner(sys.argv[1], sys.argv[2], sys.argv[3])
