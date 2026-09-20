"""
Genera tarjetas de texto (PNG con fondo semitransparente) para superponer datos clave sobre el vídeo.

Uso:
    python generar_tarjetas.py overlays.txt carpeta_salida/ [ancho] [alto]

overlays.txt: una línea por tarjeta, formato:
    inicio_seg|fin_seg|texto de la tarjeta

Genera además overlays_index.txt con "ruta_png|inicio|fin" para que ensamblar_video_v2.py lo use.
"""
import sys
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FUENTES_CANDIDATAS = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
]


def cargar_fuente(tamano: int) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES_CANDIDATAS:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def ajustar_lineas(draw: ImageDraw.ImageDraw, texto: str, fuente: ImageFont.FreeTypeFont, ancho_max: int) -> list[str]:
    palabras = texto.split()
    lineas = []
    linea_actual = ""
    for palabra in palabras:
        candidata = f"{linea_actual} {palabra}".strip()
        bbox = draw.textbbox((0, 0), candidata, font=fuente)
        if bbox[2] - bbox[0] <= ancho_max or not linea_actual:
            linea_actual = candidata
        else:
            lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)
    return lineas


def generar_tarjeta(texto: str, ancho: int, alto: int, salida: Path):
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    tamano_fuente = max(28, ancho // 26)
    fuente = cargar_fuente(tamano_fuente)

    ancho_max_texto = ancho - int(ancho * 0.16)
    lineas = ajustar_lineas(draw, texto, fuente, ancho_max_texto)

    alto_linea = int(tamano_fuente * 1.35)
    alto_bloque = alto_linea * len(lineas)
    padding_v = int(tamano_fuente * 0.9)
    padding_h = int(tamano_fuente * 1.4)

    ancho_linea_max = max(draw.textbbox((0, 0), l, font=fuente)[2] for l in lineas)
    caja_ancho = min(ancho_linea_max + padding_h * 2, ancho - int(ancho * 0.06))
    caja_alto = alto_bloque + padding_v * 2
    caja_x0 = (ancho - caja_ancho) // 2
    caja_y0 = alto - caja_alto - int(alto * 0.14)

    draw.rounded_rectangle(
        [caja_x0, caja_y0, caja_x0 + caja_ancho, caja_y0 + caja_alto],
        radius=24,
        fill=(10, 14, 30, 210),
        outline=(90, 170, 255, 255),
        width=3,
    )

    y = caja_y0 + padding_v
    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=fuente)
        ancho_texto = bbox[2] - bbox[0]
        x = (ancho - ancho_texto) // 2
        draw.text((x, y), linea, font=fuente, fill=(255, 255, 255, 255))
        y += alto_linea

    img.save(salida)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python generar_tarjetas.py <overlays.txt> <carpeta_salida> [ancho] [alto]")
        sys.exit(1)

    overlays_path = Path(sys.argv[1])
    carpeta_salida = Path(sys.argv[2])
    ancho = int(sys.argv[3]) if len(sys.argv) > 3 else 1080
    alto = int(sys.argv[4]) if len(sys.argv) > 4 else 1920

    carpeta_salida.mkdir(parents=True, exist_ok=True)
    lineas_config = [l.strip() for l in overlays_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    index_lineas = []
    for i, linea in enumerate(lineas_config, start=1):
        inicio, fin, texto = linea.split("|", 2)
        salida_png = carpeta_salida / f"tarjeta_{i:02d}.png"
        generar_tarjeta(texto, ancho, alto, salida_png)
        index_lineas.append(f"{salida_png.resolve()}|{inicio}|{fin}")
        print(f"Tarjeta generada: {salida_png} ({inicio}s-{fin}s)")

    (carpeta_salida / "overlays_index.txt").write_text("\n".join(index_lineas), encoding="utf-8")
    print(f"Índice guardado en: {carpeta_salida / 'overlays_index.txt'}")
