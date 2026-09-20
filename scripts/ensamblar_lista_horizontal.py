"""
Ensambla el sub-formato "lista horizontal" (estilo XpressTV: "25 cosas que no
sabías en N minutos"): clips de vídeo real con transiciones cruzadas + audio
narrado + subtítulos (aparte, con quemar_subtitulos.py) + cronómetro de
cuenta atrás en la esquina superior derecha.

Uso:
    python ensamblar_lista_horizontal.py carpeta_clips/ audio.mp3 salida.mp4 [ancho] [alto]

carpeta_clips/: debe contener clip_01.mp4, clip_02.mp4, ... (ver buscar_videos_pexels.py)
"""
import sys
import shutil
import subprocess
import json
from pathlib import Path

FFMPEG_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
FFPROBE_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"

TRANSICION_DUR = 0.6
FPS = 30
FUENTE_TIMER = r"C:\Windows\Fonts\segoeuib.ttf"


def resolver_bin():
    ffmpeg = shutil.which("ffmpeg") or FFMPEG_FALLBACK
    ffprobe = shutil.which("ffprobe") or FFPROBE_FALLBACK
    return ffmpeg, ffprobe


def duracion_audio(ffprobe: str, audio_path: str) -> float:
    out = subprocess.check_output([
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "json", audio_path
    ])
    return float(json.loads(out)["format"]["duration"])


def _ruta_ffmpeg_fuente(ruta: str) -> str:
    return "'" + ruta.replace("\\", "/").replace(":", "\\:") + "'"


def ensamblar(carpeta_clips: Path, duraciones: list[float], audio_path: str, salida: str, ancho: int, alto: int):
    """duraciones: duración EXACTA (segundos) que debe durar en pantalla cada
    clip, una por cada clip_NN.mp4 en orden — normalmente la duración real de
    la frase narrada correspondiente a ese dato (para que el clip en pantalla
    coincida con lo que se está diciendo, en vez de repartir el vídeo a partes
    iguales sin relación con el guion). Ver aprendizajes.md, lista_001_25_gatos."""
    ffmpeg, ffprobe = resolver_bin()
    t = TRANSICION_DUR

    clips = sorted(carpeta_clips.glob("clip_*.mp4"))
    n = len(clips)
    if n == 0:
        raise FileNotFoundError(f"No hay clips en {carpeta_clips}")
    if n != len(duraciones):
        raise ValueError(f"Número de clips ({n}) no coincide con número de duraciones ({len(duraciones)})")

    # cada clip, salvo el último, se renderiza t segundos más largo de lo que
    # se ve realmente en pantalla: ese margen es lo que consume el siguiente
    # crossfade sin robarle tiempo visible a la duración pedida.
    duraciones_render = [d + t for d in duraciones[:-1]] + [duraciones[-1]]

    inputs = []
    filtro_partes = []
    for i, (clip, dur_render) in enumerate(zip(clips, duraciones_render)):
        inputs += ["-stream_loop", "-1", "-t", f"{dur_render:.3f}", "-i", str(clip)]
        filtro_partes.append(
            f"[{i}:v]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
            f"crop={ancho}:{alto},setsar=1,fps={FPS},format=yuva420p[c{i}]"
        )

    cadena = "c0"
    offset_acum = duraciones_render[0] - t
    xfade_partes = []
    for i in range(1, n):
        origen = f"[{cadena}][c{i}]"
        destino = f"x{i}" if i < n - 1 else "vsinbadge"
        xfade_partes.append(f"{origen}xfade=transition=fade:duration={t:.3f}:offset={offset_acum:.3f}[{destino}]")
        cadena = destino
        offset_acum += duraciones_render[i] - t

    dur_total = sum(duraciones)

    if n == 1:
        filtro_partes.append("[c0]null[vsinbadge]")

    # cronómetro de cuenta atrás, arriba a la derecha
    fuente = _ruta_ffmpeg_fuente(FUENTE_TIMER)
    tamano_fuente = int(alto * 0.05)
    timer = (
        f"[vsinbadge]drawtext=fontfile={fuente}:"
        f"text='%{{eif\\:trunc({dur_total:.2f}-t)/60\\:d}}\\:%{{eif\\:mod(trunc({dur_total:.2f}-t)\\,60)\\:d\\:2}}':"
        f"fontsize={tamano_fuente}:fontcolor=white:box=1:boxcolor=0xE8720C@0.95:"
        f"boxborderw={int(tamano_fuente*0.35)}:x=w-tw-{int(ancho*0.03)}:y={int(alto*0.04)}:"
        f"enable='between(t,0,{dur_total:.2f})'[vout]"
    )

    filtro_completo = ";".join(filtro_partes) + ";" + ";".join(xfade_partes) + ";" + timer

    tmp_dir = carpeta_clips / "_tmp_horizontal"
    tmp_dir.mkdir(exist_ok=True)
    filtro_script = tmp_dir / "filtro.txt"
    filtro_script.write_text(filtro_completo, encoding="utf-8")

    video_mudo = tmp_dir / "video_mudo.mp4"
    cmd = [ffmpeg, "-y", *inputs, "-filter_complex", filtro_completo,
           "-map", "[vout]", "-r", str(FPS), "-t", f"{dur_total:.3f}", str(video_mudo)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise RuntimeError("ffmpeg falló generando el vídeo con transiciones y cronómetro")
    print(f"Vídeo con transiciones y cronómetro generado: {video_mudo}")

    cmd_final = [ffmpeg, "-y", "-i", str(video_mudo), "-i", audio_path,
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                 "-shortest", salida]
    r = subprocess.run(cmd_final, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise RuntimeError("ffmpeg falló en el ensamblado final")
    print(f"Vídeo final generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python ensamblar_lista_horizontal.py <carpeta_clips> <audio.mp3> <salida.mp4> [ancho] [alto]")
        print("(prueba manual: reparte el audio a partes iguales entre los clips; "
              "producir_video.py usa duraciones exactas por dato, no esto)")
        sys.exit(1)

    carpeta = Path(sys.argv[1])
    audio = sys.argv[2]
    salida = sys.argv[3]
    ancho = int(sys.argv[4]) if len(sys.argv) > 4 else 1920
    alto = int(sys.argv[5]) if len(sys.argv) > 5 else 1080

    _, _ffprobe = resolver_bin()
    _n = len(sorted(carpeta.glob("clip_*.mp4")))
    _dur_total = duracion_audio(_ffprobe, audio)
    _duraciones = [_dur_total / _n] * _n
    ensamblar(carpeta, _duraciones, audio, salida, ancho, alto)
