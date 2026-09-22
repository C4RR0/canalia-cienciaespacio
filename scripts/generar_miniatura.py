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


def componer(imagen_base: Image.Image, texto: str, orientacion: str) -> Image.Image:
    """Recibe una imagen base (frame real o hero IA) y le aplica el tratamiento
    de miniatura: recorte a 1280x720, degradado oscuro inferior, texto gancho
    grande con contorno negro. Compartido entre generar() (frame de vídeo) y
    generar_desde_ia() (imagen IA cinematográfica dedicada)."""
    frame = imagen_base.convert("RGB")

    ratio = max(ANCHO / frame.width, ALTO / frame.height)
    escalado = frame.resize((int(frame.width * ratio), int(frame.height * ratio)))
    ex = (escalado.width - ANCHO) // 2
    sesgo_y = 0.42 if orientacion == "vertical" else 0.5
    ey = int((escalado.height - ALTO) * sesgo_y)
    lienzo = escalado.crop((ex, ey, ex + ANCHO, ey + ALTO))
    lienzo = lienzo.convert("RGBA")

    # ligero boost de contraste/saturacion, coherente con el gradeado del cuerpo del video
    lienzo_rgb = lienzo.convert("RGB")
    lienzo_rgb = ImageEnhance.Contrast(lienzo_rgb).enhance(1.12)
    lienzo_rgb = ImageEnhance.Color(lienzo_rgb).enhance(1.20)
    lienzo = lienzo_rgb.convert("RGBA")

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
        for dx in range(-5, 6, 2):
            for dy in range(-5, 6, 2):
                draw.text((x + dx, y + dy), linea, font=fuente, fill=(0, 0, 0, 255))
        draw.text((x, y), linea, font=fuente, fill=(255, 255, 255, 255))
        y += alto_linea

    return lienzo.convert("RGB")


def generar(video_path: str, segundo: float, texto: str, salida: str, orientacion: str):
    tmp_frame = Path(salida).with_suffix(".frame.jpg")
    extraer_frame(video_path, segundo, tmp_frame)
    frame = Image.open(tmp_frame)
    resultado = componer(frame, texto, orientacion)
    resultado.save(salida, quality=92)
    tmp_frame.unlink(missing_ok=True)
    print(f"Miniatura generada: {salida}")


def generar_desde_ia(prompt_visual: str, texto: str, salida: str, orientacion: str, semilla: int = 7):
    """Genera una imagen IA cinematográfica dedicada (no reutiliza fotogramas
    del cuerpo del vídeo) como base de la miniatura: mucho más impactante que
    un frame de slideshow, al estilo de las miniaturas de canales de
    documentales/misterio profesionales (sujeto dramático + iluminación de
    cine en vez de una foto de archivo plana)."""
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    import generar_imagenes

    import re as _re
    sujeto = _re.sub(r"\b(photo|photograph|illustration|picture)\b\.?\s*(NASA)?\s*$", "", prompt_visual, flags=_re.IGNORECASE).strip()
    prompt_completo = (
        f"cinematic dramatic photo of {sujeto}, moody dramatic lighting, "
        f"high contrast, ultra detailed, 8k, photorealistic, national geographic style, "
        f"deep shadows, volumetric light, full bleed close up, no border, no frame, no watermark"
    )
    # Se pide CUADRADA (no 1280x720 directo) a propósito: el recorte "cover"
    # de componer() así SÍ recorta margen de verdad (en vez de solo reescalar
    # 1:1 sin tocar bordes), lo que elimina la marca de agua de pollinations.ai
    # que aparece pegada a la esquina inferior derecha de sus imágenes.
    tmp_ia = Path(salida).with_suffix(".hero.jpg")
    generar_imagenes.generar_imagen(prompt_completo, 1280, 1280, tmp_ia, semilla=semilla)
    hero = Image.open(tmp_ia)
    resultado = componer(hero, texto, orientacion)
    resultado.save(salida, quality=92)
    tmp_ia.unlink(missing_ok=True)
    print(f"Miniatura IA generada: {salida}")


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
