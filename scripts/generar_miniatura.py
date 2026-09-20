"""
Genera una miniatura de YouTube (1280x720) a partir de un fotograma real del vídeo
(sin subtítulos quemados) + un texto gancho grande, estilo clásico de miniatura.

Uso:
    python generar_miniatura.py <video.mp4> <segundo> "<TEXTO GANCHO>" <salida.jpg> [horizontal|vertical]
"""
import sys
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

FFMPEG_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"

ANCHO, ALTO = 1280, 720

FUENTES_BOLD = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def cargar_fuente(tamano: int) -> ImageFont.FreeTypeFont:
    for ruta in FUENTES_BOLD:
        if Path(ruta).exists():
            return ImageFont.truetype(ruta, tamano)
    return ImageFont.load_default()


def extraer_frame(video_path: str, segundo: float, salida: Path):
    ffmpeg = shutil.which("ffmpeg") or FFMPEG_FALLBACK
    cmd = [ffmpeg, "-y", "-ss", str(segundo), "-i", video_path,
           "-frames:v", "1", "-update", "1", str(salida)]
    subprocess.run(cmd, check=True, capture_output=True)


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


def generar(video_path: str, segundo: float, texto: str, salida: str, orientacion: str):
    tmp_frame = Path(salida).with_suffix(".frame.jpg")
    extraer_frame(video_path, segundo, tmp_frame)
    frame = Image.open(tmp_frame).convert("RGB")

    # Recorte a pantalla completa (llena todo el encuadre 16:9, sin barras laterales)
    ratio = max(ANCHO / frame.width, ALTO / frame.height)
    escalado = frame.resize((int(frame.width * ratio), int(frame.height * ratio)))
    ex = (escalado.width - ANCHO) // 2
    # para verticales, ancla el recorte un poco por encima del centro (el sujeto suele estar ahí)
    sesgo_y = 0.42 if orientacion == "vertical" else 0.5
    ey = int((escalado.height - ALTO) * sesgo_y)
    lienzo = escalado.crop((ex, ey, ex + ANCHO, ey + ALTO))

    lienzo = lienzo.convert("RGBA")

    # degradado oscuro inferior para legibilidad del texto
    degradado = Image.new("L", (1, ALTO), 0)
    for y in range(ALTO):
        t = max(0.0, (y - ALTO * 0.45) / (ALTO * 0.55))
        degradado.putpixel((0, y), int(190 * t))
    degradado = degradado.resize((ANCHO, ALTO))
    capa_oscura = Image.new("RGBA", (ANCHO, ALTO), (5, 5, 15, 255))
    capa_oscura.putalpha(degradado)
    lienzo = Image.alpha_composite(lienzo, capa_oscura)

    draw = ImageDraw.Draw(lienzo)
    tamano_fuente = 92
    fuente = cargar_fuente(tamano_fuente)
    lineas = ajustar_lineas(draw, texto.upper(), fuente, ANCHO - 100)
    alto_linea = int(tamano_fuente * 1.08)
    alto_bloque = alto_linea * len(lineas)
    y = ALTO - alto_bloque - 50

    for linea in lineas:
        bbox = draw.textbbox((0, 0), linea, font=fuente)
        x = (ANCHO - (bbox[2] - bbox[0])) // 2
        # contorno grueso negro
        for dx in range(-5, 6, 2):
            for dy in range(-5, 6, 2):
                draw.text((x + dx, y + dy), linea, font=fuente, fill=(0, 0, 0, 255))
        draw.text((x, y), linea, font=fuente, fill=(255, 255, 255, 255))
        y += alto_linea

    lienzo.convert("RGB").save(salida, quality=92)
    tmp_frame.unlink(missing_ok=True)
    print(f"Miniatura generada: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print('Uso: python generar_miniatura.py <video.mp4> <segundo> "<TEXTO>" <salida.jpg> [horizontal|vertical]')
        sys.exit(1)

    video = sys.argv[1]
    segundo = float(sys.argv[2])
    texto = sys.argv[3]
    salida = sys.argv[4]
    orientacion = sys.argv[5] if len(sys.argv) > 5 else "vertical"

    generar(video, segundo, texto, salida, orientacion)
