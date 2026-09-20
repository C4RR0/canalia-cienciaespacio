"""
Actualiza el título/descripción de un vídeo ya publicado (por si hace falta corregir
tildes u otros detalles tras la subida automática).

Uso:
    python actualizar_youtube.py <video_id> <titulo_file.txt> <descripcion_file.txt> <categoria_id>
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
    if len(sys.argv) < 5:
        print("Uso: python actualizar_youtube.py <video_id> <titulo_file.txt> <descripcion_file.txt> <categoria_id>")
        sys.exit(1)

    video_id = sys.argv[1]
    titulo = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
    descripcion = Path(sys.argv[3]).read_text(encoding="utf-8")
    categoria_id = sys.argv[4]

    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)

    youtube.videos().update(
        part="snippet",
        body={
            "id": video_id,
            "snippet": {
                "title": titulo,
                "description": descripcion,
                "categoryId": categoria_id,
            },
        },
    ).execute()
    print(f"Vídeo {video_id} actualizado.")
