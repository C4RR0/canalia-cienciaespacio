"""
Ensambla un vídeo a partir de una carpeta de imágenes + un audio narrado, con efecto Ken Burns
(zoom/pan lento) en cada imagen, usando ffmpeg.

Uso:
    python ensamblar_video.py carpeta_imagenes/ audio.mp3 salida.mp4 [ancho] [alto]

Reparte el audio a partes iguales entre todas las imágenes de la carpeta (ordenadas por nombre).
"""
import sys
import subprocess
import json
from pathlib import Path

FFMPEG = None  # se resuelve en tiempo de ejecución
FFPROBE = None


def resolver_ffmpeg():
    global FFMPEG, FFPROBE
    import shutil
    FFMPEG = shutil.which("ffmpeg") or r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
    FFPROBE = shutil.which("ffprobe") or r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"


def duracion_audio(audio_path: str) -> float:
    out = subprocess.check_output([
        FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "json", audio_path
    ])
    data = json.loads(out)
    return float(data["format"]["duration"])


def ensamblar(carpeta_imagenes: Path, audio_path: str, salida: str, ancho: int, alto: int):
    imagenes = sorted(carpeta_imagenes.glob("*.jpg")) + sorted(carpeta_imagenes.glob("*.png"))
    if not imagenes:
        raise FileNotFoundError(f"No hay imágenes en {carpeta_imagenes}")

    dur_total = duracion_audio(audio_path)
    dur_por_imagen = dur_total / len(imagenes)
    fps = 30

    # Genera un clip con zoom lento por cada imagen y luego los concatena
    tmp_dir = carpeta_imagenes / "_tmp_clips"
    tmp_dir.mkdir(exist_ok=True)
    lista_concat = tmp_dir / "lista.txt"
    rutas_clips = []

    for i, img in enumerate(imagenes):
        clip_out = tmp_dir / f"clip_{i:02d}.mp4"
        n_frames = int(dur_por_imagen * fps)
        zoom_expr = f"min(zoom+0.0007,1.3)"
        vf = (
            f"scale=8000:-1,"
            f"zoompan=z='{zoom_expr}':d={n_frames}:s={ancho}x{alto}:fps={fps},"
            f"format=yuv420p"
        )
        cmd = [
            FFMPEG, "-y", "-loop", "1", "-i", str(img),
            "-vf", vf, "-t", str(dur_por_imagen),
            "-r", str(fps), str(clip_out)
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        rutas_clips.append(clip_out)
        print(f"Clip generado: {clip_out}")

    with open(lista_concat, "w", encoding="utf-8") as f:
        for clip in rutas_clips:
            f.write(f"file '{clip.resolve()}'\n")

    video_mudo = tmp_dir / "video_mudo.mp4"
    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lista_concat),
        "-c", "copy", str(video_mudo)
    ], check=True, capture_output=True)

    subprocess.run([
        FFMPEG, "-y", "-i", str(video_mudo), "-i", audio_path,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", salida
    ], check=True, capture_output=True)

    print(f"Vídeo final generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python ensamblar_video.py <carpeta_imagenes> <audio.mp3> <salida.mp4> [ancho] [alto]")
        sys.exit(1)

    resolver_ffmpeg()
    carpeta = Path(sys.argv[1])
    audio = sys.argv[2]
    salida = sys.argv[3]
    ancho = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    alto = int(sys.argv[5]) if len(sys.argv) > 5 else 1920

    ensamblar(carpeta, audio, salida, ancho, alto)
