"""
Aplica una miniatura personalizada a un vídeo ya publicado.

Uso:
    python poner_miniatura.py <video_id> <miniatura.jpg>
"""
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python poner_miniatura.py <video_id> <miniatura.jpg>")
        sys.exit(1)

    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)
    youtube.thumbnails().set(
        videoId=sys.argv[1],
        media_body=MediaFileUpload(sys.argv[2]),
    ).execute()
    print(f"Miniatura aplicada a {sys.argv[1]}")
