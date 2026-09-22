"""
Ensambla un vídeo educativo de calidad: imágenes con efecto Ken Burns + transiciones cruzadas suaves
+ audio narrado + (opcional) tarjetas de datos clave superpuestas.

Uso:
    python ensamblar_video_v2.py carpeta_imagenes/ audio.mp3 salida.mp4 [ancho] [alto] [overlays_index.txt]
"""
import sys
import shutil
import subprocess
import json
from pathlib import Path

FFMPEG_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"
FFPROBE_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"

TRANSICION_DUR = 0.7
FPS = 30


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


def cargar_secuencia(secuencia_path: Path, dur_total: float, t: float, dur_min: float = 2.5):
    lineas = [l.strip() for l in secuencia_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    items = []
    for linea in lineas:
        ruta, frac = linea.rsplit("|", 1)
        items.append((Path(ruta), float(frac)))
    items.sort(key=lambda x: x[1])

    imagenes = [p for p, _ in items]
    fracciones = [f for _, f in items] + [1.0]
    duraciones = []
    for i in range(len(imagenes)):
        dur_base = (fracciones[i + 1] - fracciones[i]) * dur_total
        duraciones.append(max(dur_base + t, dur_min + t))
    return imagenes, duraciones


def ensamblar(carpeta_imagenes: Path, audio_path: str, salida: str, ancho: int, alto: int, overlays_index: Path | None, secuencia_path: Path | None = None):
    ffmpeg, ffprobe = resolver_bin()
    dur_total = duracion_audio(ffprobe, audio_path)
    t = TRANSICION_DUR

    if secuencia_path and secuencia_path.exists():
        imagenes, duraciones = cargar_secuencia(secuencia_path, dur_total, t)
    else:
        imagenes = sorted(carpeta_imagenes.glob("*.jpg")) + sorted(carpeta_imagenes.glob("*.png"))
        imagenes = [p for p in imagenes if not p.name.startswith("tarjeta_")]
        n0 = len(imagenes)
        dur_clip = (dur_total + (n0 - 1) * t) / n0
        duraciones = [dur_clip] * n0

    n = len(imagenes)
    if n == 0:
        raise FileNotFoundError(f"No hay imágenes en {carpeta_imagenes}")

    inputs = []
    filtro_partes = []
    for i, (img, dur_clip) in enumerate(zip(imagenes, duraciones)):
        n_frames = int(dur_clip * FPS)
        inputs += ["-loop", "1", "-t", f"{dur_clip:.3f}", "-i", str(img)]
        direccion = "in" if i % 2 == 0 else "out"
        if direccion == "in":
            zoom_expr = "min(zoom+0.0006,1.2)"
        else:
            zoom_expr = "if(eq(on,1),1.2,max(zoom-0.0006,1.0))"
        # Gradeado cinematográfico: mas contraste/saturacion + nitidez leve
        # (compensa fotos reales algo planas o de baja resolucion de archivo)
        # + vineta sutil para dirigir la mirada al centro, estilo documental.
        filtro_partes.append(
            f"[{i}:v]scale=8000:-1,zoompan=z='{zoom_expr}':d={n_frames}:s={ancho}x{alto}:fps={FPS},"
            f"eq=contrast=1.12:saturation=1.22:brightness=0.01:gamma=1.03,"
            f"unsharp=5:5:0.5,vignette=PI/5.5,"
            f"format=yuva420p,setsar=1[c{i}]"
        )

    # Encadena las transiciones xfade
    cadena = "c0"
    offset_acum = duraciones[0] - t
    xfade_partes = []
    for i in range(1, n):
        origen = f"[{cadena}][c{i}]"
        destino = f"x{i}" if i < n - 1 else "vout"
        xfade_partes.append(f"{origen}xfade=transition=fade:duration={t:.3f}:offset={offset_acum:.3f}[{destino}]")
        cadena = destino
        offset_acum += duraciones[i] - t

    filtro_completo = ";".join(filtro_partes) + ";" + ";".join(xfade_partes)

    tmp_dir = carpeta_imagenes / "_tmp_v2"
    tmp_dir.mkdir(exist_ok=True)
    video_mudo = tmp_dir / "video_mudo.mp4"
    filtro_script = tmp_dir / "filtro.txt"
    filtro_script.write_text(filtro_completo, encoding="utf-8")

    cmd = [ffmpeg, "-y", *inputs, "-filter_complex", filtro_completo,
           "-map", "[vout]", "-r", str(FPS), "-t", f"{dur_total:.3f}", str(video_mudo)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise RuntimeError("ffmpeg falló generando el vídeo con transiciones")
    print(f"Vídeo con transiciones generado: {video_mudo}")

    video_con_overlays = video_mudo
    if overlays_index and overlays_index.exists():
        video_con_overlays = tmp_dir / "video_overlays.mp4"
        lineas = [l.strip() for l in overlays_index.read_text(encoding="utf-8").splitlines() if l.strip()]
        ov_inputs = []
        ov_filtro = ["[0:v]null[base0]"]
        etiqueta_actual = "base0"
        for idx, linea in enumerate(lineas, start=1):
            png_path, inicio, fin = linea.split("|")
            ov_inputs += ["-i", png_path]
            siguiente = f"base{idx}"
            ov_filtro.append(
                f"[{etiqueta_actual}][{idx}:v]overlay=0:0:enable='between(t,{inicio},{fin})'[{siguiente}]"
            )
            etiqueta_actual = siguiente
        filtro_ov_completo = ";".join(ov_filtro)
        filtro_ov_script = tmp_dir / "filtro_overlays.txt"
        filtro_ov_script.write_text(filtro_ov_completo, encoding="utf-8")

        cmd_ov = [ffmpeg, "-y", "-i", str(video_mudo), *ov_inputs,
                  "-filter_complex", filtro_ov_completo,
                  "-map", f"[{etiqueta_actual}]", str(video_con_overlays)]
        r = subprocess.run(cmd_ov, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-4000:])
            raise RuntimeError("ffmpeg falló aplicando las tarjetas de datos")
        print(f"Vídeo con tarjetas de datos generado: {video_con_overlays}")

    cmd_final = [ffmpeg, "-y", "-i", str(video_con_overlays), "-i", audio_path,
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                 "-shortest", salida]
    r = subprocess.run(cmd_final, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-4000:])
        raise RuntimeError("ffmpeg falló en el ensamblado final")
    print(f"Vídeo final generado: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python ensamblar_video_v2.py <carpeta_imagenes> <audio.mp3> <salida.mp4> [ancho] [alto] [overlays_index.txt] [secuencia.txt]")
        sys.exit(1)

    carpeta = Path(sys.argv[1])
    audio = sys.argv[2]
    salida = sys.argv[3]
    ancho = int(sys.argv[4]) if len(sys.argv) > 4 else 1080
    alto = int(sys.argv[5]) if len(sys.argv) > 5 else 1920
    overlays = Path(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] != "-" else None
    secuencia = Path(sys.argv[7]) if len(sys.argv) > 7 else None

    ensamblar(carpeta, audio, salida, ancho, alto, overlays, secuencia)
