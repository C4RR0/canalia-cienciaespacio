"""
Lista todos los vídeos del canal (id, título, duración aproximada por tipo).

Uso:
    python listar_videos.py
"""
from pathlib import Path
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


def main():
    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)

    canal = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_playlist = canal["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    pagina = None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist,
            maxResults=50,
            pageToken=pagina,
        ).execute()
        for item in resp["items"]:
            videos.append({
                "id": item["contentDetails"]["videoId"],
                "titulo": item["snippet"]["title"],
                "publicado": item["contentDetails"].get("videoPublishedAt", ""),
            })
        pagina = resp.get("nextPageToken")
        if not pagina:
            break

    for v in sorted(videos, key=lambda x: x["publicado"]):
        print(f"{v['id']}\t{v['publicado']}\t{v['titulo']}")


if __name__ == "__main__":
    main()
