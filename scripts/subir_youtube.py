"""
Sube un vídeo a YouTube de forma 100% automática vía la API oficial (sin navegador,
sin límite de tamaño, sin intervención manual). Reutiliza token.json indefinidamente
(se refresca solo) tras la autenticación inicial hecha con autenticar_youtube.py.

Uso:
    python subir_youtube.py <video.mp4> <titulo_file.txt> <descripcion_file.txt> <tags_csv> <categoria_id> <privacidad> [miniatura.jpg]

El título y la descripción se leen de archivo (no como argumento directo) para evitar
problemas de codificación de tildes/eñes al pasar por PowerShell.

privacidad: private | unlisted | public
categoria_id: 27 = Educación, 28 = Ciencia y tecnología, 24 = Entretenimiento (usa 27 o 28 salvo que quieras otra)
"""
import os
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = Path(__file__).parent.parent
TOKEN_PATH = BASE / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def cargar_credenciales() -> Credentials:
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def subir(video_path: str, titulo: str, descripcion: str, tags: list[str],
          categoria_id: str, privacidad: str, miniatura: str | None = None) -> str:
    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": titulo,
            "description": descripcion,
            "tags": tags,
            "categoryId": categoria_id,
        },
        "status": {
            "privacyStatus": privacidad,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Los Shorts (pocos MB) van de una vez. Los largos (recopilaciones, >400 MB)
    # por trozos: de una vez, la sesión de subida dio 410 "Gone" al final
    # (8/10/2026), aunque el vídeo sí llegó.
    grande = os.path.getsize(video_path) > 100 * 1024 * 1024
    media = MediaFileUpload(video_path, chunksize=16 * 1024 * 1024 if grande else -1,
                            resumable=True, mimetype="video/mp4")
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Subiendo... {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Vídeo publicado: https://youtu.be/{video_id}")

    if miniatura and Path(miniatura).exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(miniatura)).execute()
            print("Miniatura personalizada aplicada.")
        except Exception as e:
            # No debe tumbar la subida: el vídeo ya está publicado aunque falle la miniatura
            # (p.ej. canal sin verificar por teléfono -> 403 forbidden).
            print(f"AVISO: no se pudo aplicar la miniatura personalizada ({e}). El vídeo sí se publicó.")

    return video_id


if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("Uso: python subir_youtube.py <video.mp4> <titulo_file.txt> <descripcion_file.txt> <tags_csv> <categoria_id> <privacidad> [miniatura.jpg]")
        sys.exit(1)

    video_path = sys.argv[1]
    titulo = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
    descripcion = Path(sys.argv[3]).read_text(encoding="utf-8")
    tags = [t.strip() for t in sys.argv[4].split(",") if t.strip()]
    categoria_id = sys.argv[5]
    privacidad = sys.argv[6]
    miniatura = sys.argv[7] if len(sys.argv) > 7 else None

    subir(video_path, titulo, descripcion, tags, categoria_id, privacidad, miniatura)
