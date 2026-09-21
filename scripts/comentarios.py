"""
Lista comentarios nuevos sin respuesta del canal, y permite publicar
respuestas. La generación del TEXTO de cada respuesta la hace quien
ejecuta este script con criterio (persona o sesión de Claude Code) — este
módulo solo automatiza la parte mecánica (leer la API, detectar qué está
sin responder, publicar la respuesta), no inventa el contenido.

Uso:
    python comentarios.py listar
        Imprime en JSON los comentarios de nivel superior sin ninguna
        respuesta del propio canal todavía.

    python comentarios.py responder <comment_id> "<texto de la respuesta>"
        Publica una respuesta a ese comentario.
"""
import sys
import json
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).parent.parent
TOKEN_PATH = BASE / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def cargar_credenciales() -> Credentials:
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _canal_propio(youtube) -> str:
    resp = youtube.channels().list(part="id", mine=True).execute()
    return resp["items"][0]["id"]


def listar_sin_responder(youtube, mi_canal_id: str) -> list[dict]:
    pendientes = []
    resp = youtube.commentThreads().list(
        part="snippet,replies", allThreadsRelatedToChannelId=mi_canal_id,
        order="time", maxResults=50, textFormat="plainText",
    ).execute()
    for item in resp.get("items", []):
        top = item["snippet"]["topLevelComment"]["snippet"]
        # ya respondido por el propio canal si alguna respuesta es del dueño
        respuestas = item.get("replies", {}).get("comments", [])
        ya_respondido = any(
            r["snippet"]["authorChannelId"]["value"] == mi_canal_id for r in respuestas
        )
        if ya_respondido or top["authorChannelId"]["value"] == mi_canal_id:
            continue
        pendientes.append({
            "comment_id": item["snippet"]["topLevelComment"]["id"],
            "video_id": top["videoId"],
            "autor": top["authorDisplayName"],
            "texto": top["textDisplay"],
            "publicado": top["publishedAt"],
            "likes": top["likeCount"],
        })
    return pendientes


def responder(youtube, comment_id: str, texto: str):
    youtube.comments().insert(
        part="snippet",
        body={"snippet": {"parentId": comment_id, "textOriginal": texto}},
    ).execute()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)

    accion = sys.argv[1]
    if accion == "listar":
        mi_id = _canal_propio(youtube)
        pendientes = listar_sin_responder(youtube, mi_id)
        print(json.dumps(pendientes, ensure_ascii=False, indent=2))
    elif accion == "responder":
        if len(sys.argv) < 4:
            print("Uso: python comentarios.py responder <comment_id> <texto>")
            sys.exit(1)
        responder(youtube, sys.argv[2], sys.argv[3])
        print("Respuesta publicada.")
    else:
        print(f"Acción desconocida: {accion}")
        sys.exit(1)
