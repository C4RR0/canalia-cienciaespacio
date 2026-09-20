"""
Quema (incrusta) un archivo .srt sobre un vídeo, con estilo grande y centrado típico de shorts.

Uso:
    python quemar_subtitulos.py video.mp4 subtitulos.srt salida.mp4 [posicion]

posicion: "abajo" (defecto) o "arriba" (útil cuando las tarjetas de datos ocupan la parte baja)
"""
import sys
import shutil
import subprocess
from pathlib import Path

FFMPEG_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"


def escapar_ruta_ffmpeg(ruta: str) -> str:
    # ffmpeg necesita las rutas de subtítulos en formato POSIX con los dos puntos
    # de la unidad escapados, dentro del filtro -vf subtitles=...
    ruta_posix = ruta.replace("\\", "/")
    return ruta_posix.replace(":", "\\:")


def quemar(video_path: str, srt_path: str, salida: str, posicion: str = "abajo", ancho: int = 1080, alto: int = 1920):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).parent))
    from srt_a_ass import convertir as srt_a_ass_convertir

    ffmpeg = shutil.which("ffmpeg") or FFMPEG_FALLBACK

    ass_path = str(Path(srt_path).with_suffix(".ass"))
    srt_a_ass_convertir(srt_path, ass_path, ancho, alto, posicion)
    ass_escapado = escapar_ruta_ffmpeg(str(Path(ass_path).resolve()))

    vf = f"ass='{ass_escapado}'"

    cmd = [ffmpeg, "-y", "-i", video_path, "-vf", vf, "-c:a", "copy", salida]
    subprocess.run(cmd, check=True)
    print(f"Vídeo con subtítulos generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python quemar_subtitulos.py <video.mp4> <subtitulos.srt> <salida.mp4> [posicion: abajo|arriba] [ancho] [alto]")
        sys.exit(1)

    posicion = sys.argv[4] if len(sys.argv) > 4 else "abajo"
    ancho = int(sys.argv[5]) if len(sys.argv) > 5 else 1080
    alto = int(sys.argv[6]) if len(sys.argv) > 6 else 1920
    quemar(sys.argv[1], sys.argv[2], sys.argv[3], posicion, ancho, alto)
