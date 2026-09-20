"""
Genera una foto de perfil de canal con más impacto visual: gradiente radial vibrante,
símbolo con efecto de brillo/neón y acento de destello.

Uso:
    python generar_logo_v2.py salida.png
"""
import sys
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

TAMANO = 1024

# paleta: núcleo magenta/rosa brillante -> morado profundo -> casi negro en bordes
NUCLEO = (255, 90, 150)
MEDIO = (124, 40, 180)
BORDE = (18, 8, 40)

FUENTES_CANDIDATAS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def cargar_fuente(tamano: int) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES_CANDIDATAS:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def generar_fondo_radial(tamano: int, centro_rel=(0.42, 0.38)) -> Image.Image:
    fondo = Image.new("RGB", (tamano, tamano))
    px = fondo.load()
    cx, cy = tamano * centro_rel[0], tamano * centro_rel[1]
    max_dist = math.hypot(max(cx, tamano - cx), max(cy, tamano - cy))
    for y in range(tamano):
        for x in range(tamano):
            d = math.hypot(x - cx, y - cy) / max_dist
            if d < 0.5:
                color = lerp_color(NUCLEO, MEDIO, d / 0.5)
            else:
                color = lerp_color(MEDIO, BORDE, (d - 0.5) / 0.5)
            px[x, y] = color
    return fondo


def dibujar_estrella(draw, cx, cy, radio_ext, radio_int, puntas, color):
    puntos = []
    for i in range(puntas * 2):
        ang = math.pi / puntas * i - math.pi / 2
        r = radio_ext if i % 2 == 0 else radio_int
        puntos.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(puntos, fill=color)


def generar_logo(salida: str, texto: str = "?"):
    fondo = generar_fondo_radial(TAMANO)
    img = fondo.convert("RGBA")

    fuente = cargar_fuente(int(TAMANO * 0.6))

    tmp_draw = ImageDraw.Draw(img)
    bbox = tmp_draw.textbbox((0, 0), texto, font=fuente)
    ancho_texto = bbox[2] - bbox[0]
    alto_texto = bbox[3] - bbox[1]
    x = (TAMANO - ancho_texto) / 2 - bbox[0]
    y = (TAMANO - alto_texto) / 2 - bbox[1] - TAMANO * 0.015

    # --- capa de brillo/neón detrás del símbolo ---
    capa_glow = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(capa_glow)
    draw_glow.text((x, y), texto, font=fuente, fill=(255, 235, 160, 255))
    glow_grande = capa_glow.filter(ImageFilter.GaussianBlur(38))
    glow_medio = capa_glow.filter(ImageFilter.GaussianBlur(16))
    img = Image.alpha_composite(img, glow_grande)
    img = Image.alpha_composite(img, glow_medio)

    # --- sombra de contacto sutil ---
    capa_sombra = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    draw_sombra = ImageDraw.Draw(capa_sombra)
    offset = int(TAMANO * 0.01)
    draw_sombra.text((x + offset, y + offset * 1.6), texto, font=fuente, fill=(0, 0, 0, 160))
    capa_sombra = capa_sombra.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, capa_sombra)

    # --- símbolo principal con relleno degradado (blanco -> amarillo suave) ---
    capa_texto = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    draw_texto = ImageDraw.Draw(capa_texto)
    draw_texto.text((x, y), texto, font=fuente, fill=(255, 255, 255, 255))

    degradado_texto = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    px = degradado_texto.load()
    color_arriba = (255, 255, 255)
    color_abajo = (255, 214, 120)
    for yy in range(int(y) if y > 0 else 0, TAMANO):
        t = max(0.0, min(1.0, (yy - y) / max(alto_texto, 1)))
        c = lerp_color(color_arriba, color_abajo, t)
        for xx in range(TAMANO):
            px[xx, yy] = (c[0], c[1], c[2], 255)
    mascara = capa_texto.split()[3]
    degradado_texto.putalpha(mascara)
    img = Image.alpha_composite(img, degradado_texto)

    # --- borde fino brillante alrededor del símbolo ---
    contorno = capa_texto.filter(ImageFilter.MaxFilter(5))
    contorno = ImageChops.subtract(contorno.split()[3], capa_texto.split()[3])
    capa_contorno = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 0))
    capa_contorno.putalpha(contorno)
    r, g, b, a = capa_contorno.split()
    blanco = Image.new("RGBA", (TAMANO, TAMANO), (255, 255, 255, 0))
    blanco.putalpha(a)
    img = Image.alpha_composite(img, blanco)

    # --- chispas decorativas alrededor, sin chocar con el símbolo ---
    draw_final = ImageDraw.Draw(img)
    dibujar_estrella(draw_final, TAMANO * 0.80, TAMANO * 0.18, TAMANO * 0.032, TAMANO * 0.013, 4, (255, 255, 255, 220))
    dibujar_estrella(draw_final, TAMANO * 0.16, TAMANO * 0.24, TAMANO * 0.02, TAMANO * 0.008, 4, (255, 255, 255, 170))
    dibujar_estrella(draw_final, TAMANO * 0.82, TAMANO * 0.76, TAMANO * 0.018, TAMANO * 0.007, 4, (255, 255, 255, 160))
    dibujar_estrella(draw_final, TAMANO * 0.14, TAMANO * 0.78, TAMANO * 0.026, TAMANO * 0.011, 4, (255, 255, 255, 200))

    # --- viñeta final para dar profundidad en los bordes ---
    vineta = Image.new("L", (TAMANO, TAMANO), 0)
    draw_v = ImageDraw.Draw(vineta)
    draw_v.ellipse([-TAMANO * 0.15, -TAMANO * 0.15, TAMANO * 1.15, TAMANO * 1.15], fill=255)
    vineta = vineta.filter(ImageFilter.GaussianBlur(90))
    negro = Image.new("RGBA", (TAMANO, TAMANO), (0, 0, 0, 255))
    img = Image.composite(img, negro, vineta)

    img.convert("RGB").save(salida, quality=95)
    print(f"Logo generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python generar_logo_v2.py <salida.png> [texto]")
        sys.exit(1)

    salida = sys.argv[1]
    texto = sys.argv[2] if len(sys.argv) > 2 else "?"
    generar_logo(salida, texto)
