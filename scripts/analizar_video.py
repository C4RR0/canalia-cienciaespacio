"""
Consulta el rendimiento real de los vídeos publicados (vistas, duración media de
visualización, % retención, likes) vía YouTube Analytics, para poder comparar
formatos/temas y decidir qué repetir o descartar.

Uso:
    python analizar_video.py                  -> todos los vídeos del canal
    python analizar_video.py <video_id> [...]  -> solo esos vídeos
"""
import sys
import json
from datetime import date, timedelta
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


def listar_todos_los_videos(youtube) -> list[dict]:
    canal = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads = canal["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    videos, pagina = [], None
    while True:
        resp = youtube.playlistItems().list(
            part="snippet,contentDetails", playlistId=uploads, maxResults=50, pageToken=pagina
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
    return videos


def metricas_video_analytics(analytics, video_id: str) -> dict:
    """Retención/duración media vía YouTube Analytics. En canales nuevos/pequeños
    esta API puede devolver 'rows' vacío (no es un error, es falta de datos
    procesados) — nunca tratar esa respuesta vacía como "0 vistas reales",
    para eso está metricas_video_data() que usa la API de datos (fiable)."""
    fin = date.today()
    inicio = fin - timedelta(days=365)
    resp = analytics.reports().query(
        ids="channel==MINE",
        startDate=inicio.isoformat(),
        endDate=fin.isoformat(),
        metrics="averageViewDuration,averageViewPercentage",
        filters=f"video=={video_id}",
    ).execute()
    if not resp.get("rows"):
        return {"averageViewDuration": None, "averageViewPercentage": None}
    fila = resp["rows"][0]
    claves = [h["name"] for h in resp["columnHeaders"]]
    return dict(zip(claves, fila))


def metricas_video_data(youtube, video_ids: list[str]) -> dict:
    """Vistas/likes/comentarios reales vía la API de datos (statistics),
    fiable y sin el retraso de procesamiento de Analytics."""
    resultado = {}
    for i in range(0, len(video_ids), 50):
        lote = video_ids[i:i + 50]
        resp = youtube.videos().list(part="statistics", id=",".join(lote)).execute()
        for item in resp["items"]:
            resultado[item["id"]] = item["statistics"]
    return resultado


def main():
    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    ids_pedidos = sys.argv[1:]
    if ids_pedidos:
        videos = [{"id": vid, "titulo": vid, "publicado": ""} for vid in ids_pedidos]
    else:
        videos = listar_todos_los_videos(youtube)

    stats = metricas_video_data(youtube, [v["id"] for v in videos])

    resultados = []
    for v in videos:
        st = stats.get(v["id"], {})
        an = metricas_video_analytics(analytics, v["id"])
        views = int(st.get("viewCount", 0))
        likes = int(st.get("likeCount", 0))
        comments = int(st.get("commentCount", 0))
        fila = {**v, "views": views, "likes": likes, "comments": comments, **an}
        resultados.append(fila)
        retencion = an.get("averageViewPercentage")
        retencion_str = f"{retencion:>5.1f}%" if retencion is not None else "  n/d "
        print(f"{v['id']}  vistas={views:>6}  "
              f"retencion={retencion_str}  "
              f"likes={likes:>3}  comentarios={comments:>3}  {v['titulo'][:55]}")

    (BASE / "salidas" / "analiticas.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
