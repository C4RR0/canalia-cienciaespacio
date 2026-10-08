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

EXTENSIONES = {".jpg", ".png", ".mp4"}
TRANSICION_DUR = 0.7
TRANSICION_RAPIDA = 0.25
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


def ensamblar(carpeta_imagenes: Path, audio_path: str, salida: str, ancho: int, alto: int, overlays_index: Path | None, secuencia_path: Path | None = None, musica_path: Path | None = None, plano_max: float | None = None):
    ffmpeg, ffprobe = resolver_bin()
    dur_total = duracion_audio(ffprobe, audio_path)
    t = TRANSICION_DUR

    if secuencia_path and secuencia_path.exists():
        imagenes, duraciones = cargar_secuencia(secuencia_path, dur_total, t)
    else:
        # Un hueco img_NN puede ser una foto o un clip de vídeo real (img_NN.mp4):
        # se ordenan juntos por nombre para respetar el orden del guion.
        imagenes = sorted((p for p in carpeta_imagenes.iterdir() if p.suffix.lower() in EXTENSIONES),
                          key=lambda p: p.name)
        imagenes = [p for p in imagenes if not p.name.startswith("tarjeta_")]
        n0 = len(imagenes)
        dur_clip = (dur_total + (n0 - 1) * t) / n0
        duraciones = [dur_clip] * n0

    n = len(imagenes)
    if n == 0:
        raise FileNotFoundError(f"No hay imágenes en {carpeta_imagenes}")

    # Ritmo rápido (Shorts): cada imagen se trocea en varios "planos" de como
    # mucho plano_max segundos, cada uno con un encuadre y zoom distintos, para
    # que haya un cambio visual cada ~2-3 s (el algoritmo de Shorts 2026 premia
    # la retención, y 9 s sobre la misma imagen hacía que la gente deslizara).
    # (ax, ay, zoom_inicial, zoom_final): alterna plano general y primer plano
    # en zonas distintas de la imagen, como cortes de cámara reales.
    anclas = [(0.5, 0.5, 1.0, 1.15), (0.3, 0.35, 1.75, 1.6), (0.5, 0.5, 1.2, 1.05),
              (0.7, 0.65, 1.6, 1.75), (0.5, 0.3, 1.1, 1.3)]
    planos = []  # (imagen, duracion, ax, ay, direccion | (zoom_ini, zoom_fin))
    if plano_max:
        t = TRANSICION_RAPIDA
        k = 0
        for img, dur_clip in zip(imagenes, duraciones):
            if img.suffix.lower() == ".mp4":
                # El vídeo real ya tiene movimiento: un solo plano, sin trocear.
                planos.append((img, dur_clip, 0.5, 0.5, None))
                continue
            util = dur_clip - t
            partes = max(1, round(util / plano_max))
            for _ in range(partes):
                ax, ay, z0, z1 = anclas[k % len(anclas)]
                planos.append((img, util / partes + t, ax, ay, (z0, z1)))
                k += 1
        escala = 4000
    else:
        for i, (img, dur_clip) in enumerate(zip(imagenes, duraciones)):
            planos.append((img, dur_clip, 0.5, 0.5, "in" if i % 2 == 0 else "out"))
        escala = 8000
    duraciones = [p[1] for p in planos]
    n = len(planos)

    inputs = []
    filtro_partes = []
    for i, (img, dur_clip, ax, ay, direccion) in enumerate(planos):
        n_frames = int(dur_clip * FPS)
        gradeado = (f"eq=contrast=1.12:saturation=1.22:brightness=0.01:gamma=1.03,"
                    f"unsharp=5:5:0.5,vignette=PI/5.5,format=yuva420p,setsar=1")
        if img.suffix.lower() == ".mp4":
            # Clip real: se repite si es más corto que el hueco y se queda sin su
            # audio. Entero y centrado sobre una copia suya desenfocada (estilo
            # Short): recortar un clip 16:9 a vertical lo ampliaría ~3x y se
            # vería pixelado (los de Commons suelen ser de 480-720p).
            inputs += ["-stream_loop", "-1", "-t", f"{dur_clip:.3f}", "-i", str(img)]
            filtro_partes.append(
                f"[{i}:v]fps={FPS},trim=duration={dur_clip:.3f},setpts=PTS-STARTPTS,split[f{i}][b{i}];"
                f"[b{i}]scale={ancho}:{alto}:force_original_aspect_ratio=increase,crop={ancho}:{alto},"
                f"boxblur=20:2,eq=brightness=-0.12[fondo{i}];"
                f"[f{i}]scale={ancho}:{alto}:force_original_aspect_ratio=decrease[frente{i}];"
                f"[fondo{i}][frente{i}]overlay=(W-w)/2:(H-h)/2,{gradeado}[c{i}]"
            )
            continue
        inputs += ["-loop", "1", "-t", f"{dur_clip:.3f}", "-i", str(img)]
        if plano_max:
            # Planos cortos: zoom más marcado para que se note el movimiento.
            z0, z1 = direccion
            zoom_expr = f"{z0}+({z1}-{z0})*on/{n_frames}"
            pos = f":x='(iw-iw/zoom)*{ax}':y='(ih-ih/zoom)*{ay}'"
        else:
            if direccion == "in":
                zoom_expr = "min(zoom+0.0006,1.2)"
            else:
                zoom_expr = "if(eq(on,1),1.2,max(zoom-0.0006,1.0))"
            pos = ""
        # Gradeado cinematográfico: mas contraste/saturacion + nitidez leve
        # (compensa fotos reales algo planas o de baja resolucion de archivo)
        # + vineta sutil para dirigir la mirada al centro, estilo documental.
        filtro_partes.append(
            f"[{i}:v]scale={escala}:-1,zoompan=z='{zoom_expr}'{pos}:d={n_frames}:s={ancho}x{alto}:fps={FPS},"
            f"{gradeado}[c{i}]"
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

    if musica_path and Path(musica_path).exists():
        # Cama musical de fondo, en bucle si hace falta y recortada a la duracion
        # exacta de la narracion, con fade in/out y volumen bajo (no debe competir
        # con la voz). amix con normalize=0 para controlar el nivel a mano en vez
        # de que ffmpeg divida ambas pistas a la mitad automaticamente.
        fade_out_inicio = max(dur_total - 1.5, 0)
        filtro_audio = (
            f"[2:a]aloop=loop=-1:size=2147483647,atrim=0:{dur_total:.3f},"
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out_inicio:.3f}:d=1.5,"
            f"volume=0.13[musica];"
            f"[1:a]volume=1.0[voz];"
            f"[voz][musica]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
        )
        cmd_final = [ffmpeg, "-y", "-i", str(video_con_overlays), "-i", audio_path, "-i", str(musica_path),
                     "-filter_complex", filtro_audio, "-map", "0:v", "-map", "[aout]",
                     "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                     "-shortest", salida]
    else:
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
