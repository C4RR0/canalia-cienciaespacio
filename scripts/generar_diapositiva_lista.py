"""
Genera una diapositiva a pantalla completa para vídeos tipo "listicle"
(ej. "25 cosas que no sabías en 1 minuto"): número grande + texto del dato,
sobre un fondo degradado de color según el tema del vídeo.

Uso:
    python generar_diapositiva_lista.py <numero> "<texto del dato>" <salida.jpg> [ancho] [alto] [tema]

tema: espacio | naturaleza | historia | familiar | adulto | curiosidades (por defecto)
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FUENTES_BOLD = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]
FUENTES_BLACK = [
    r"C:\Windows\Fonts\seguibl.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]

PALETAS = {
    "espacio":       ((10, 8, 35), (35, 15, 70), (130, 100, 255)),
    "naturaleza":    ((5, 30, 25), (10, 60, 45), (110, 220, 150)),
    "historia":      ((35, 20, 8), (60, 35, 12), (230, 160, 70)),
    "familiar":      ((20, 30, 60), (255, 120, 60), (255, 210, 60)),
    "adulto":        ((12, 12, 14), (35, 10, 14), (200, 40, 50)),
    "curiosidades":  ((8, 10, 30), (25, 15, 55), (90, 170, 255)),
}


def cargar_fuente(rutas, tamano: int) -> ImageFont.FreeTypeFont:
    for ruta in rutas:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def degradado_diagonal(ancho: int, alto: int, c1, c2):
    img = Image.new("RGB", (ancho, alto), c1)
    px = img.load()
    for y in range(alto):
        t = y / max(1, alto - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(0, ancho, 4):
            px[x, y] = (r, g, b)
            if x + 1 < ancho: px[x + 1, y] = (r, g, b)
            if x + 2 < ancho: px[x + 2, y] = (r, g, b)
            if x + 3 < ancho: px[x + 3, y] = (r, g, b)
    return img


def ajustar_lineas(draw, texto, fuente, ancho_max):
    palabras = texto.split()
    lineas, actual = [], ""
    for palabra in palabras:
        candidata = f"{actual} {palabra}".strip()
        bbox = draw.textbbox((0, 0), candidata, font=fuente)
        if bbox[2] - bbox[0] <= ancho_max or not actual:
            actual = candidata
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def generar(numero: int, texto: str, salida: str, ancho: int, alto: int, tema: str):
    c1, c2, acento = PALETAS.get(tema, PALETAS["curiosidades"])
    lienzo = degradado_diagonal(ancho, alto, c1, c2).convert("RGBA")
    draw = ImageDraw.Draw(lienzo)

    # deja libre el 25% inferior para los subtítulos quemados encima
    zona_util_alto = int(alto * 0.72)

    # número grande arriba
    fuente_numero = cargar_fuente(FUENTES_BLACK, int(ancho * 0.30))
    num_txt = str(numero)
    bbox = draw.textbbox((0, 0), num_txt, font=fuente_numero)
    nx = (ancho - (bbox[2] - bbox[0])) // 2
    ny = int(alto * 0.06)
    for dx in range(-4, 5, 2):
        for dy in range(-4, 5, 2):
            draw.text((nx + dx, ny + dy), num_txt, font=fuente_numero, fill=(0, 0, 0, 140))
    draw.text((nx, ny), num_txt, font=fuente_numero, fill=(*acento, 255))

    # texto del dato, centrado en la zona útil
    tamano_fuente = int(ancho * 0.062)
    fuente = cargar_fuente(FUENTES_BOLD, tamano_fuente)
    ancho_max = int(ancho * 0.86)
    lineas = ajustar_lineas(draw, texto.upper(), fuente, ancho_max)
    alto_linea = int(tamano_fuente * 1.18)
    alto_bloque = alto_linea * len(lineas)
    y = ny + int(ancho * 0.34) + (zona_util_alto - (ny + int(ancho * 0.34)) - alto_bloque) // 2
    y = max(y, ny + int(ancho * 0.36))

    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=fuente)
        x = (ancho - (bbox[2] - bbox[0])) // 2
        for dx in range(-4, 5, 2):
            for dy in range(-4, 5, 2):
                draw.text((x + dx, y + dy), linea, font=fuente, fill=(0, 0, 0, 200))
        draw.text((x, y), linea, font=fuente, fill=(255, 255, 255, 255))
        y += alto_linea

    lienzo.convert("RGB").save(salida, quality=93)
    print(f"Diapositiva generada: {salida}")


def generar_miniatura_lista(cantidad: int, hook: str, salida: str, tema: str):
    """Miniatura 1280x720 dedicada para el formato 'lista': número grande + gancho,
    SIN extraer un fotograma del vídeo (evita que el texto de una diapositiva de
    fondo choque y se solape con el texto de la miniatura)."""
    ancho, alto = 1280, 720
    c1, c2, acento = PALETAS.get(tema, PALETAS["curiosidades"])
    lienzo = degradado_diagonal(ancho, alto, c1, c2).convert("RGBA")
    draw = ImageDraw.Draw(lienzo)

    fuente_numero = cargar_fuente(FUENTES_BLACK, int(alto * 0.62))
    num_txt = str(cantidad)
    bbox = draw.textbbox((0, 0), num_txt, font=fuente_numero)
    nx = int(ancho * 0.06)
    ny = (alto - (bbox[3] - bbox[1])) // 2 - bbox[1]
    for dx in range(-5, 6, 2):
        for dy in range(-5, 6, 2):
            draw.text((nx + dx, ny + dy), num_txt, font=fuente_numero, fill=(0, 0, 0, 160))
    draw.text((nx, ny), num_txt, font=fuente_numero, fill=(*acento, 255))

    tamano_fuente = int(alto * 0.135)
    fuente = cargar_fuente(FUENTES_BOLD, tamano_fuente)
    ancho_txt_max = int(ancho * 0.46)
    x_texto = int(ancho * 0.50)
    lineas = ajustar_lineas(draw, hook.upper(), fuente, ancho_txt_max)
    alto_linea = int(tamano_fuente * 1.12)
    alto_bloque = alto_linea * len(lineas)
    y = (alto - alto_bloque) // 2

    for linea in lineas:
        for dx in range(-4, 5, 2):
            for dy in range(-4, 5, 2):
                draw.text((x_texto + dx, y + dy), linea, font=fuente, fill=(0, 0, 0, 220))
        draw.text((x_texto, y), linea, font=fuente, fill=(255, 255, 255, 255))
        y += alto_linea

    lienzo.convert("RGB").save(salida, quality=93)
    print(f"Miniatura de lista generada: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print('Uso: python generar_diapositiva_lista.py <numero> "<texto>" <salida.jpg> [ancho] [alto] [tema]')
        sys.exit(1)

    numero = int(sys.argv[1])
    texto = sys.argv[2]
    salida = sys.argv[3]
    ancho = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    alto = int(sys.argv[5]) if len(sys.argv) > 5 else 1920
    tema = sys.argv[6] if len(sys.argv) > 6 else "curiosidades"

    generar(numero, texto, salida, ancho, alto, tema)
