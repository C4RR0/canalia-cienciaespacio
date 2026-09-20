"""
Comprueba si el canal cumple los requisitos actuales del Programa de Socios de YouTube (YPP):
- 500 suscriptores
- Y (3.000 horas de visualización en los últimos 12 meses O 3.000.000 de vistas de Shorts
  en los últimos 90 días)

Imprime un resumen y termina con código de salida 0 si YA se cumplen ambos requisitos
(útil para que un script que lo invoque decida si debe avisar al usuario), o 1 si no.

Uso:
    python comprobar_monetizacion.py
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
ESTADO_PATH = BASE / "estado_monetizacion.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

SUB_OBJETIVO = 500
HORAS_OBJETIVO = 3000
VISTAS_SHORTS_OBJETIVO = 3_000_000


def cargar_credenciales() -> Credentials:
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def obtener_canal_id(youtube):
    resp = youtube.channels().list(part="id,statistics", mine=True).execute()
    item = resp["items"][0]
    return item["id"], int(item["statistics"]["subscriberCount"])


def obtener_horas_vision_12m(analytics, channel_id: str) -> float:
    fin = date.today()
    inicio = fin - timedelta(days=365)
    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=inicio.isoformat(),
        endDate=fin.isoformat(),
        metrics="estimatedMinutesWatched",
    ).execute()
    minutos = resp.get("rows", [[0]])[0][0] if resp.get("rows") else 0
    return minutos / 60


def obtener_vistas_shorts_90d(analytics, channel_id: str) -> int:
    fin = date.today()
    inicio = fin - timedelta(days=90)
    resp = analytics.reports().query(
        ids=f"channel=={channel_id}",
        startDate=inicio.isoformat(),
        endDate=fin.isoformat(),
        metrics="views",
        dimensions="creatorContentType",
    ).execute()
    for fila in resp.get("rows", []):
        if fila[0] == "SHORTS":
            return int(fila[1])
    return 0


def main():
    creds = cargar_credenciales()
    youtube = build("youtube", "v3", credentials=creds)
    analytics = build("youtubeAnalytics", "v2", credentials=creds)

    channel_id, suscriptores = obtener_canal_id(youtube)
    horas = obtener_horas_vision_12m(analytics, channel_id)
    vistas_shorts = obtener_vistas_shorts_90d(analytics, channel_id)

    cumple_horas_o_shorts = horas >= HORAS_OBJETIVO or vistas_shorts >= VISTAS_SHORTS_OBJETIVO
    cumple_subs = suscriptores >= SUB_OBJETIVO
    elegible = cumple_subs and cumple_horas_o_shorts

    resultado = {
        "suscriptores": suscriptores,
        "horas_vision_12m": round(horas, 1),
        "vistas_shorts_90d": vistas_shorts,
        "cumple_suscriptores": cumple_subs,
        "cumple_horas_o_shorts": cumple_horas_o_shorts,
        "elegible_monetizacion": elegible,
    }

    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    ESTADO_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.exit(0 if elegible else 1)


if __name__ == "__main__":
    main()
