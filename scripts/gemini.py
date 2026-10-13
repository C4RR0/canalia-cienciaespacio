"""
Acceso a Gemini con el plan GRATUITO de Google AI Studio (decisión del usuario
del 13/10/2026: nada de pago). Lo usan responder_auto.py y qa_imagenes.py.

El modelo se elige solo entre los "flash" que ofrezca la clave (los nombres
cambian a menudo), saltando al siguiente si uno está saturado o tarda, y
empezando después por el último que funcionó. GEMINI_MODEL lo fuerza.

Requiere GEMINI_API_KEY (gratis en aistudio.google.com).
"""
import base64
import io
import json
import os
import time

import requests

API_GEMINI = "https://generativelanguage.googleapis.com/v1beta"
_modelos = None


def modelos() -> list[str]:
    """Gemini "flash" que admiten generateContent, del más nuevo al más viejo
    (los "lite" al final, como último recurso)."""
    global _modelos
    if _modelos:
        return _modelos
    if os.environ.get("GEMINI_MODEL"):
        _modelos = [os.environ["GEMINI_MODEL"]]
        return _modelos
    resp = requests.get(f"{API_GEMINI}/models", params={"key": os.environ["GEMINI_API_KEY"],
                                                        "pageSize": 1000}, timeout=30)
    resp.raise_for_status()
    excluir = ("image", "tts", "audio", "live", "embedding", "thinking", "exp", "preview")
    candidatos = [m["name"].removeprefix("models/") for m in resp.json().get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])
                  and "flash" in m["name"] and not any(x in m["name"] for x in excluir)]
    if not candidatos:
        raise RuntimeError("La clave no ofrece ningún modelo Gemini flash")

    def version(nombre):
        try:
            return float(nombre.split("-")[1])
        except (IndexError, ValueError):
            return 0.0

    _modelos = sorted(candidatos, key=lambda n: ("lite" in n, -version(n), len(n)))
    print(f"Modelos: {', '.join(_modelos)}")
    return _modelos


def generar(cuerpo: dict, rondas: int = 4) -> dict:
    """Prueba los modelos en orden; si uno está saturado (429/500/503) o tarda,
    pasa al siguiente (cada modelo tiene su propio cupo gratis). Si fallan todos,
    espera a que se renueve el cupo por minuto y da otra ronda."""
    ultimo = None
    for ronda in range(rondas):
        if ronda:
            print(f"  [aviso] todos los modelos saturados, espera {60 * ronda} s")
            time.sleep(60 * ronda)
        for modelo in list(modelos()):
            try:
                resp = requests.post(f"{API_GEMINI}/models/{modelo}:generateContent",
                                     params={"key": os.environ["GEMINI_API_KEY"]},
                                     json=cuerpo, timeout=120)
            except (requests.Timeout, requests.ConnectionError) as e:
                ultimo = e
                print(f"  [aviso] {modelo}: {type(e).__name__}, se prueba otro")
                continue
            if resp.ok:
                # El que funcionó pasa a ser el primero para las siguientes llamadas.
                _modelos.remove(modelo)
                _modelos.insert(0, modelo)
                return resp.json()
            ultimo = resp
            print(f"  [aviso] {modelo} devolvió {resp.status_code}, se prueba otro")
    if isinstance(ultimo, Exception):
        raise ultimo
    ultimo.raise_for_status()


def parte_imagen(img, lado_max: int = 768) -> dict:
    """Parte de contenido con una imagen PIL, reducida para gastar menos cuota."""
    img = img.convert("RGB")
    img.thumbnail((lado_max, lado_max))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return {"inline_data": {"mime_type": "image/jpeg",
                            "data": base64.b64encode(buf.getvalue()).decode()}}


def json_estructurado(sistema: str, partes: list, esquema: dict) -> dict | None:
    """Devuelve la respuesta como dict según `esquema` (tipos en mayúsculas,
    formato de Gemini), o None si el modelo no terminó bien."""
    candidato = generar({
        "systemInstruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": partes}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseSchema": esquema},
    })["candidates"][0]
    if candidato.get("finishReason") != "STOP":
        print(f"  [aviso] finishReason={candidato.get('finishReason')}, se omite")
        return None
    return json.loads("".join(p.get("text", "") for p in candidato["content"]["parts"]))
