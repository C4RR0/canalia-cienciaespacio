"""
Comprime las pausas largas de un audio TTS (edge-tts deja ~1s de silencio en cada coma/punto,
lo que suena entrecortado) dejando pausas naturales y breves.

Uso:
    python suavizar_audio.py entrada.mp3 salida.mp3 [pausa_max_ms]
"""
import sys
from pydub import AudioSegment
from pydub.silence import detect_silence

PAUSA_MAX_DEFECTO_MS = 220  # pausa máxima que se deja tras comprimir


def suavizar(entrada: str, salida: str, pausa_max_ms: int = PAUSA_MAX_DEFECTO_MS):
    audio = AudioSegment.from_file(entrada)

    silencios = detect_silence(audio, min_silence_len=180, silence_thresh=audio.dBFS - 20, seek_step=10)
    print(f"Silencios detectados: {len(silencios)}")

    if not silencios:
        audio.export(salida, format="mp3", bitrate="192k")
        print("Sin silencios largos que comprimir; se copia tal cual.")
        return

    resultado = AudioSegment.empty()
    cursor = 0
    for inicio, fin in silencios:
        resultado += audio[cursor:inicio]
        duracion_pausa = fin - inicio
        resultado += AudioSegment.silent(duration=min(duracion_pausa, pausa_max_ms))
        cursor = fin
    resultado += audio[cursor:]

    resultado.export(salida, format="mp3", bitrate="192k")
    dur_antes = len(audio) / 1000
    dur_despues = len(resultado) / 1000
    print(f"Duración: {dur_antes:.1f}s -> {dur_despues:.1f}s")
    print(f"Audio suavizado guardado en: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python suavizar_audio.py <entrada.mp3> <salida.mp3> [pausa_max_ms]")
        sys.exit(1)

    entrada = sys.argv[1]
    salida = sys.argv[2]
    pausa_max = int(sys.argv[3]) if len(sys.argv) > 3 else PAUSA_MAX_DEFECTO_MS

    suavizar(entrada, salida, pausa_max)
