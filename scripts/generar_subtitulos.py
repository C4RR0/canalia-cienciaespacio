"""
Transcribe un audio a subtítulos .srt usando faster-whisper (gratis, funciona en local, sin API).

Uso:
    python generar_subtitulos.py audio.mp3 salida.srt [modelo]

Modelos disponibles (de más rápido/impreciso a más lento/preciso):
    tiny, base, small, medium, large-v3
Para español, "small" suele dar buen equilibrio velocidad/precisión en CPU.
"""
import sys
from pathlib import Path
from faster_whisper import WhisperModel


def formatear_tiempo(segundos: float) -> str:
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = segundos % 60
    milisegundos = int((segs - int(segs)) * 1000)
    return f"{horas:02d}:{minutos:02d}:{int(segs):02d},{milisegundos:03d}"


def generar_srt(audio_path: str, salida_path: str, modelo: str = "small"):
    model = WhisperModel(modelo, device="cpu", compute_type="int8")
    segmentos, info = model.transcribe(audio_path, language="es", vad_filter=True)

    with open(salida_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segmentos, start=1):
            inicio = formatear_tiempo(seg.start)
            fin = formatear_tiempo(seg.end)
            texto = seg.text.strip()
            f.write(f"{i}\n{inicio} --> {fin}\n{texto}\n\n")
            print(f"[{inicio} -> {fin}] {texto}")

    print(f"\nSubtítulos guardados en: {salida_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python generar_subtitulos.py <audio.mp3> <salida.srt> [modelo]")
        sys.exit(1)

    audio = sys.argv[1]
    salida = sys.argv[2]
    modelo = sys.argv[3] if len(sys.argv) > 3 else "small"

    generar_srt(audio, salida, modelo)
