"""
Voz con el TTS de Gemini (plan GRATUITO de Google AI Studio), para que el canal
no suene a la voz de serie de Microsoft que usan miles de canales de IA
(riesgo de "contenido inauténtico", ver aprendizajes.md 2026-10-15).

El modelo se elige solo entre los "tts" que ofrezca la clave, sin los "pro"
(no son gratis). Devuelve PCM 24 kHz mono 16 bit, que se pasa a mp3 con ffmpeg.

Uso:
    python voz_gemini.py guion.txt salida.mp3 [voz]
    python voz_gemini.py --modelos      (lista los modelos tts disponibles)

Requiere GEMINI_API_KEY.
"""
import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

API_GEMINI = "https://generativelanguage.googleapis.com/v1beta"
VOZ_POR_DEFECTO = "Charon"

# Estilo en el formato corto de la documentación de Gemini TTS ("Say ...: <texto>").
# Los modelos tts no aceptan systemInstruction (400) y una instrucción larga en
# español la LEÍAN en voz alta (prueba del 15/10); si aun así se cuela, lo frena
# el control de duración de sintetizar().
ESTILO = ("Say in Castilian Spanish from Spain, as a warm, energetic storyteller "
          "full of genuine amazement, at a brisk pace: ")
PALABRAS_POR_SEGUNDO = 2.6  # ritmo medio de AlvaroNeural en el canal
MARGEN_DURACION = 1.3


def modelos_tts() -> list[str]:
    resp = requests.get(f"{API_GEMINI}/models", params={"key": os.environ["GEMINI_API_KEY"],
                                                        "pageSize": 1000}, timeout=30)
    resp.raise_for_status()
    nombres = [m["name"].removeprefix("models/") for m in resp.json().get("models", [])
               if "tts" in m["name"] and "pro" not in m["name"]]

    def version(nombre):
        try:
            return float(nombre.split("-")[1])
        except (IndexError, ValueError):
            return 0.0

    return sorted(nombres, key=lambda n: (-version(n), "preview" in n, len(n)))


def sintetizar(texto: str, salida_mp3: str, voz: str = VOZ_POR_DEFECTO,
               estilo: str = ESTILO, rondas: int = 3) -> str:
    """Genera salida_mp3 y devuelve el modelo usado. Lanza excepción si no puede."""
    cuerpo = {
        "contents": [{"parts": [{"text": estilo + texto}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}},
        },
    }
    ultimo = None
    for ronda in range(rondas):
        if ronda:
            time.sleep(30 * ronda)
        for modelo in modelos_tts():
            resp = requests.post(f"{API_GEMINI}/models/{modelo}:generateContent",
                                 params={"key": os.environ["GEMINI_API_KEY"]},
                                 json=cuerpo, timeout=180)
            if not resp.ok:
                ultimo = f"{modelo}: {resp.status_code} {resp.text[:300]}"
                print(f"  [aviso] {ultimo}")
                continue
            partes = resp.json()["candidates"][0]["content"]["parts"]
            datos = next((p["inlineData"]["data"] for p in partes if "inlineData" in p), None)
            if not datos:
                ultimo = f"{modelo}: respuesta sin audio"
                continue
            with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as f:
                f.write(base64.b64decode(datos))
                pcm = f.name
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", "24000",
                            "-ac", "1", "-i", pcm, "-b:a", "192k", salida_mp3], check=True)
            os.unlink(pcm)
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                        "-of", "csv=p=0", salida_mp3],
                                       capture_output=True, text=True).stdout)
            maximo = len(texto.split()) / PALABRAS_POR_SEGUNDO * MARGEN_DURACION + 2
            if dur > maximo:
                ultimo = f"{modelo}: {dur:.1f} s, demasiado para el texto (máx {maximo:.1f} s)"
                print(f"  [aviso] {ultimo}")
                continue
            return modelo
    raise RuntimeError(f"Gemini TTS no disponible ({ultimo})")


if __name__ == "__main__":
    if sys.argv[1:] == ["--modelos"]:
        print("\n".join(modelos_tts()))
        sys.exit(0)
    texto = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
    voz = sys.argv[3] if len(sys.argv) > 3 else VOZ_POR_DEFECTO
    print(f"Audio generado (Gemini {sintetizar(texto, sys.argv[2], voz)}, voz {voz}): {sys.argv[2]}")
