"""
Convierte marcadores.txt (fraccion|texto) en un overlays.txt (inicio|fin|texto) real,
usando la duración final del audio, y separa las tarjetas que quedarían demasiado cerca.

Uso:
    python convertir_marcadores.py marcadores.txt audio_final.mp3 overlays.txt [duracion_tarjeta_seg]
"""
import sys
import shutil
import subprocess
import json
from pathlib import Path

FFPROBE_FALLBACK = r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"
SEPARACION_MINIMA = 1.0


def duracion_audio(audio_path: str) -> float:
    ffprobe = shutil.which("ffprobe") or FFPROBE_FALLBACK
    out = subprocess.check_output([
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "json", audio_path
    ])
    return float(json.loads(out)["format"]["duration"])


def convertir(marcadores_path: str, audio_path: str, salida_path: str, duracion_tarjeta: float = 4.5):
    dur_total = duracion_audio(audio_path)
    lineas = [l.strip() for l in Path(marcadores_path).read_text(encoding="utf-8").splitlines() if l.strip()]

    eventos = []
    ultimo_fin = -999.0
    for linea in lineas:
        fraccion_str, texto = linea.split("|", 1)
        inicio = float(fraccion_str) * dur_total
        if inicio < ultimo_fin + SEPARACION_MINIMA:
            inicio = ultimo_fin + SEPARACION_MINIMA
        fin = min(inicio + duracion_tarjeta, dur_total - 0.2)
        if fin <= inicio:
            continue
        eventos.append((inicio, fin, texto))
        ultimo_fin = fin

    with open(salida_path, "w", encoding="utf-8") as f:
        for inicio, fin, texto in eventos:
            f.write(f"{inicio:.2f}|{fin:.2f}|{texto}\n")

    print(f"Duración audio: {dur_total:.1f}s")
    print(f"Overlays generados: {len(eventos)} -> {salida_path}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python convertir_marcadores.py <marcadores.txt> <audio_final.mp3> <overlays.txt> [duracion_tarjeta_seg]")
        sys.exit(1)

    dur_tarjeta = float(sys.argv[4]) if len(sys.argv) > 4 else 4.5
    convertir(sys.argv[1], sys.argv[2], sys.argv[3], dur_tarjeta)
