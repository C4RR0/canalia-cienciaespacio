"""
Guarda una foto diaria de las métricas del canal en metricas/ (sin IA).

- metricas/canal.csv     : fecha, suscriptores, vistas totales, nº de vídeos
- metricas/videos.csv    : fecha, video_id, publicado, duracion_s, vistas, likes, comentarios, titulo

Lo ejecuta el workflow .github/workflows/metricas.yml una vez al día; el
histórico acumulado permite ver si cada cambio de estrategia mejora o no
(comparar vistas a 24/48/72 h de vídeos publicados antes y después).

Uso:
    python scripts/snapshot_metricas.py
"""
import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parent.parent
DIR = BASE / os.environ.get("METRICAS_DIR", "metricas")  # metricas_en = canal inglés


def _segundos(iso: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0) if m else 0


def _append(ruta: Path, cabecera: list[str], filas: list[list]):
    nuevo = not ruta.exists()
    with ruta.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(cabecera)
        w.writerows(filas)


def main():
    creds = Credentials.from_authorized_user_file(str(BASE / os.environ.get("YOUTUBE_TOKEN_FILE", "token.json")))
    if not creds.valid:
        creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)

    canal = yt.channels().list(part="statistics,contentDetails", mine=True).execute()["items"][0]
    st = canal["statistics"]
    fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    ids, token = [], None
    subidas = canal["contentDetails"]["relatedPlaylists"]["uploads"]
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=subidas,
                                    maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        token = r.get("nextPageToken")
        if not token:
            break

    filas = []
    for k in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,statistics,contentDetails",
                                  id=",".join(ids[k:k + 50])).execute()["items"]:
            s = v["statistics"]
            filas.append([fecha, v["id"], v["snippet"]["publishedAt"], _segundos(v["contentDetails"]["duration"]),
                          s.get("viewCount", 0), s.get("likeCount", 0), s.get("commentCount", 0),
                          v["snippet"]["title"]])

    DIR.mkdir(exist_ok=True)
    _append(DIR / "canal.csv", ["fecha", "suscriptores", "vistas", "videos"],
            [[fecha, st.get("subscriberCount"), st.get("viewCount"), st.get("videoCount")]])
    _append(DIR / "videos.csv", ["fecha", "video_id", "publicado", "duracion_s", "vistas", "likes",
                                 "comentarios", "titulo"], filas)
    print(f"{fecha}: {st.get('subscriberCount')} subs, {st.get('viewCount')} vistas, {len(filas)} vídeos")
    _analytics(creds, fecha)


def _analytics(creds, fecha: str):
    """Suscriptores ganados y % visto por vídeo (YouTube Analytics), para medir
    experimentos como el cierre con invitación a suscribirse (13/10/2026).
    Necesita el scope yt-analytics.readonly; si el token no lo tiene, avisa y sigue."""
    try:
        a = build("youtubeAnalytics", "v2", credentials=creds)
        r = a.reports().query(ids="channel==MINE", startDate="2026-09-01", endDate=fecha,
                              metrics="views,subscribersGained,averageViewPercentage",
                              dimensions="video", sort="-views", maxResults=200).execute()
    except Exception as e:
        print(f"AVISO: sin datos de Analytics ({str(e)[:120]})")
        return
    _append(DIR / "videos_analytics.csv",
            ["fecha", "video_id", "vistas", "subs_ganados", "porcentaje_visto"],
            [[fecha, *fila] for fila in r.get("rows", [])])
    print(f"Analytics: {len(r.get('rows', []))} vídeos")

    # Enganche del gancho (15/10/2026): la API no da "vistos frente a deslizados", pero sí
    # engagedViews (vistas que pasan de los primeros segundos). engagedViews/vistas mide lo
    # mismo: si el gancho retiene. Y la duración media en SEGUNDOS, que pesa más que el %.
    try:
        r = a.reports().query(ids="channel==MINE", startDate="2026-09-01", endDate=fecha,
                              metrics="views,engagedViews,averageViewDuration",
                              dimensions="video", sort="-views", maxResults=200).execute()
    except Exception as e:
        print(f"AVISO: sin engagedViews ({str(e)[:120]})")
        return
    _append(DIR / "videos_enganche.csv",
            ["fecha", "video_id", "vistas", "vistas_comprometidas", "segundos_vistos_media"],
            [[fecha, *fila] for fila in r.get("rows", [])])


if __name__ == "__main__":
    sys.exit(main())
