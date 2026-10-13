"""
Responde SOLO (sin sesión de Claude Code) a los comentarios nuevos del canal.
Pensado para GitHub Actions: lee los comentarios sin respuesta con
comentarios.py, pide a Claude una respuesta por comentario usando como
contexto el título y la descripción del vídeo, y la publica.

La IA es Gemini con el plan GRATUITO de Google AI Studio (decisión del
usuario del 13/10/2026: nada de pago). GitHub Models, la primera opción, se
retiró el 30/07/2026. El modelo se elige solo entre los "flash" que ofrezca la
clave (los nombres cambian a menudo), saltando al siguiente si uno está
saturado; GEMINI_MODEL lo fuerza si hace falta.

Reglas que sigue la IA (aprendidas respondiendo a mano):
- Solo datos del propio vídeo o muy conocidos; si no está seguro, no aporta
  datos nuevos (lección del 28/09: dos datos erróneos sobre Vesna).
- Spam, insultos, enlaces o comentarios sin sentido -> no se responde.

Uso:
    python responder_auto.py            # responde de verdad
    python responder_auto.py --prueba   # solo imprime lo que respondería
    python responder_auto.py --probar-modelo  # responde a un comentario inventado

Requiere token.json (YouTube) y GEMINI_API_KEY (gratis en aistudio.google.com).
"""
import json
import os
import sys
import time
from pathlib import Path

import requests
from googleapiclient.discovery import build

from comentarios import _canal_propio, cargar_credenciales, listar_sin_responder, responder

CANAL = "Sabías Qué"
MAX_POR_EJECUCION = 20
API_GEMINI = "https://generativelanguage.googleapis.com/v1beta"
_modelos = None
# comentarios que la IA decidió no responder, para no gastar cuota en ellos
IGNORADOS = Path(__file__).parent.parent / "comentarios_ignorados.txt"

SISTEMA = f"""Eres quien lleva el canal de YouTube "{CANAL}" (Shorts de curiosidades de ciencia, \
naturaleza y espacio, en español de España). Respondes a comentarios de tus vídeos.

Cómo responder:
- Cercano, natural y breve: 1-3 frases. Tutea. Como mucho un emoji.
- Si preguntan algo, contesta usando lo que dice el vídeo (título y descripción). Puedes añadir \
un dato solo si es muy conocido y estás completamente seguro; si no, no inventes nada: di que \
es buena pregunta o que lo investigarás.
- Si corrigen un dato y tienen razón, agradéceselo y reconócelo. Si no estás seguro, agradece \
el aporte sin discutir.
- Si es un elogio, agradece y, cuando encaje, invita a ver más curiosidades del canal.
- No pidas suscripciones en todas las respuestas; como mucho de vez en cuando y con naturalidad.
- Nunca pongas enlaces.
- Responde en el idioma del comentario.

No respondas (responder=false) a: spam, insultos u odio, enlaces o autopromoción, comentarios \
sin sentido, o temas que no tengan nada que ver y puedan generar polémica (política, religión)."""

ESQUEMA = {
    "type": "OBJECT",
    "properties": {
        "responder": {"type": "BOOLEAN"},
        "respuesta": {"type": "STRING"},
    },
    "required": ["responder", "respuesta"],
}


def modelos() -> list[str]:
    """Gemini "flash" de texto que admiten generateContent, del más nuevo al más
    viejo (los "lite" al final, como último recurso)."""
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


def generar(cuerpo: dict) -> dict:
    """Prueba los modelos en orden; ante saturación (429/503/500) reintenta una vez
    y pasa al siguiente."""
    ultimo = None
    for modelo in modelos():
        for intento in range(2):
            try:
                resp = requests.post(f"{API_GEMINI}/models/{modelo}:generateContent",
                                     params={"key": os.environ["GEMINI_API_KEY"]},
                                     json=cuerpo, timeout=60)
            except (requests.Timeout, requests.ConnectionError) as e:
                ultimo = e
                print(f"  [aviso] {modelo}: {type(e).__name__}, se prueba otro")
                break
            if resp.ok:
                return resp.json()
            ultimo = resp
            if resp.status_code not in (429, 500, 503):
                break
            time.sleep(10)
        else:
            print(f"  [aviso] {modelo} devolvió {ultimo.status_code}, se prueba otro")
    if isinstance(ultimo, Exception):
        raise ultimo
    ultimo.raise_for_status()


def info_videos(youtube, ids: list[str]) -> dict:
    info = {}
    for i in range(0, len(ids), 50):
        resp = youtube.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()
        for v in resp.get("items", []):
            info[v["id"]] = {
                "titulo": v["snippet"]["title"],
                "descripcion": v["snippet"]["description"][:1500],
            }
    return info


def redactar(video: dict, comentario: dict) -> dict | None:
    contenido = (
        f"Vídeo: {video.get('titulo', '(desconocido)')}\n"
        f"Descripción del vídeo:\n{video.get('descripcion', '')}\n\n"
        f"Comentario de {comentario['autor']}:\n{comentario['texto']}"
    )
    candidato = generar({
        "systemInstruction": {"parts": [{"text": SISTEMA}]},
        "contents": [{"role": "user", "parts": [{"text": contenido}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "responseSchema": ESQUEMA},
    })["candidates"][0]
    if candidato.get("finishReason") != "STOP":
        print(f"  [aviso] finishReason={candidato.get('finishReason')}, se omite")
        return None
    return json.loads("".join(p.get("text", "") for p in candidato["content"]["parts"]))


def main():
    if "--probar-modelo" in sys.argv:
        video = {"titulo": "Las orcas cazan tiburones blancos para comerse solo el hígado",
                 "descripcion": "Las orcas de Sudáfrica abren al tiburón y se comen solo el hígado."}
        print(redactar(video, {"autor": "@prueba", "texto": "¿Y por qué solo el hígado? 😮"}))
        return
    prueba = "--prueba" in sys.argv
    youtube = build("youtube", "v3", credentials=cargar_credenciales())
    mi_id = _canal_propio(youtube)
    ignorados = set(IGNORADOS.read_text(encoding="utf-8").split()) if IGNORADOS.exists() else set()
    pendientes = [c for c in listar_sin_responder(youtube, mi_id)
                  if c["comment_id"] not in ignorados][:MAX_POR_EJECUCION]
    print(f"{len(pendientes)} comentarios sin responder")
    if not pendientes:
        return
    if not os.environ.get("GEMINI_API_KEY"):
        print("Falta el secret GEMINI_API_KEY: no se responde nada.")
        return

    videos = info_videos(youtube, sorted({c["video_id"] for c in pendientes}))
    errores = 0
    for c in pendientes:
        print(f"\n[{c['autor']}] {c['texto']}")
        try:
            r = redactar(videos.get(c["video_id"], {}), c)
        except requests.RequestException as e:
            print(f"  [error API] {e}")
            errores += 1
            continue
        if r is None:
            continue
        if not r["responder"] or not r["respuesta"].strip():
            print("  -> no se responde")
            if not prueba:
                with IGNORADOS.open("a", encoding="utf-8") as f:
                    f.write(c["comment_id"] + "\n")
            continue
        print(f"  -> {r['respuesta']}")
        if not prueba:
            responder(youtube, c["comment_id"], r["respuesta"].strip())
    if errores == len(pendientes):
        sys.exit(1)


if __name__ == "__main__":
    main()
