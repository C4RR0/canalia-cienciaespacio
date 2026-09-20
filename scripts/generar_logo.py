"""
Genera una foto de perfil de canal: fondo con degradado circular + símbolo grande centrado.

Uso:
    python generar_logo.py salida.png [texto]
"""
import sys
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

TAMANO = 1024

COLOR_A = (124, 58, 237)    # morado
COLOR_B = (249, 115, 22)    # naranja

FUENTES_CANDIDATAS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def cargar_fuente(tamano: int) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES_CANDIDATAS:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def generar_fondo_degradado(tamano: int, color_a, color_b) -> Image.Image:
    fondo = Image.new("RGB", (tamano, tamano))
    px = fondo.load()
    for y in range(tamano):
        for x in range(tamano):
            # degradado diagonal
            t = (x + y) / (2 * tamano)
            r = int(color_a[0] + (color_b[0] - color_a[0]) * t)
            g = int(color_a[1] + (color_b[1] - color_a[1]) * t)
            b = int(color_a[2] + (color_b[2] - color_a[2]) * t)
            px[x, y] = (r, g, b)
    return fondo


def generar_logo(salida: str, texto: str = "?"):
    fondo = generar_fondo_degradado(TAMANO, COLOR_A, COLOR_B)
    img = fondo.convert("RGBA")
    draw = ImageDraw.Draw(img)

    # sombra del texto
    fuente = cargar_fuente(int(TAMANO * 0.56))
    bbox = draw.textbbox((0, 0), texto, font=fuente)
    ancho_texto = bbox[2] - bbox[0]
    alto_texto = bbox[3] - bbox[1]
    x = (TAMANO - ancho_texto) / 2 - bbox[0]
    y = (TAMANO - alto_texto) / 2 - bbox[1]

    capa_sombra = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    draw_sombra = ImageDraw.Draw(capa_sombra)
    offset = int(TAMANO * 0.012)
    draw_sombra.text((x + offset, y + offset * 2), texto, font=fuente, fill=(0, 0, 0, 130))
    capa_sombra = capa_sombra.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, capa_sombra)

    draw = ImageDraw.Draw(img)
    draw.text((x, y), texto, font=fuente, fill=(255, 255, 255, 255))

    img.convert("RGB").save(salida, quality=95)
    print(f"Logo generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python generar_logo.py <salida.png> [texto]")
        sys.exit(1)

    salida = sys.argv[1]
    texto = sys.argv[2] if len(sys.argv) > 2 else "?"
    generar_logo(salida, texto)
