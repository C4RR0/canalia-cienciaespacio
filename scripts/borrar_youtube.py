"""
Borra un vídeo de YouTube (por id). Útil para corregir subidas con errores de contenido.

Uso:
    python borrar_youtube.py <video_id>
"""
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).parent.parent
TOKEN_PATH = BASE / "token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def cargar_credenciales() -> Credentials:
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python borrar_youtube.py <video_id>")
        sys.exit(1)

    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)
    youtube.videos().delete(id=sys.argv[1]).execute()
    print(f"Vídeo {sys.argv[1]} borrado.")
