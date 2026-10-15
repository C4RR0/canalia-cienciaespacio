"""
Compara voces para el canal (15/10/2026): genera el guion de un config con
varias voces de Gemini TTS y con la actual (AlvaroNeural) y, para cada una,
mide duración, si whisper entiende bien el texto (palabras acertadas) y pide
a Gemini que la escuche y puntúe acento de España, naturalidad y si suena a
"voz de IA de serie". Deja los mp3 en pruebas_voz/ para escucharlos.

Uso:
    python probar_voces.py produccion_config/<id>.json Charon Fenrir ...
"""
import asyncio
import base64
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gemini  # noqa: E402
import generar_audio  # noqa: E402
import voz_gemini  # noqa: E402

SALIDA = Path("pruebas_voz")


def palabras(t):
    return re.findall(r"\w+", t.lower())


def duracion(mp3):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", mp3], capture_output=True, text=True).stdout
    return float(out.strip())


def puntuar(mp3):
    datos = base64.b64encode(Path(mp3).read_bytes()).decode()
    return gemini.json_estructurado(
        "Eres un productor de audio exigente que evalúa locuciones para Shorts de YouTube "
        "en español de España. Sé crítico y concreto.",
        [{"inline_data": {"mime_type": "audio/mp3", "data": datos}},
         {"text": "Escucha esta locución y puntúa de 1 a 10: acento_espana (10 = español "
                  "de España nativo, 1 = claramente latino o extranjero), naturalidad "
                  "(10 = parece una persona real), enganche (10 = da ganas de seguir "
                  "escuchando), suena_ia_de_serie (10 = suena a la típica voz TTS de los "
                  "canales automáticos). Añade un comentario breve con el defecto principal."}],
        {"type": "OBJECT", "properties": {
            "acento_espana": {"type": "INTEGER"}, "naturalidad": {"type": "INTEGER"},
            "enganche": {"type": "INTEGER"}, "suena_ia_de_serie": {"type": "INTEGER"},
            "comentario": {"type": "STRING"}},
         "required": ["acento_espana", "naturalidad", "enganche", "suena_ia_de_serie",
                      "comentario"]})


def main():
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    texto = cfg["guion"].strip()
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "guion.txt").write_text(texto, encoding="utf-8")
    print("Modelos TTS:", ", ".join(voz_gemini.modelos_tts()))

    pruebas = []
    mp3 = SALIDA / "alvaro.mp3"
    asyncio.run(generar_audio.generar(str(SALIDA / "guion.txt"), str(mp3), "es-ES-AlvaroNeural"))
    pruebas.append(("AlvaroNeural (actual)", mp3))
    for voz in sys.argv[2:]:
        mp3 = SALIDA / f"gemini_{voz}.mp3"
        try:
            modelo = voz_gemini.sintetizar(texto, str(mp3), voz)
            pruebas.append((f"{voz} ({modelo})", mp3))
        except Exception as e:
            print(f"{voz}: FALLO {e}")

    from faster_whisper import WhisperModel
    whisper = WhisperModel("small", device="cpu", compute_type="int8")
    ref = palabras(texto)
    filas = []
    for nombre, mp3 in pruebas:
        segs, _ = whisper.transcribe(str(mp3), language="es")
        oido = palabras(" ".join(s.text for s in segs))
        acierto = difflib.SequenceMatcher(None, ref, oido).ratio()
        try:
            nota = puntuar(mp3) or {}
        except Exception as e:
            nota = {"comentario": f"sin nota ({e})"}
        filas.append({"voz": nombre, "segundos": round(duracion(mp3), 1),
                      "whisper_acierto": round(acierto, 3), **nota})
        print(json.dumps(filas[-1], ensure_ascii=False))
    (SALIDA / "resultados.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1),
                                            encoding="utf-8")


if __name__ == "__main__":
    main()
