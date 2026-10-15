"""Comprueba qué métricas de enganche de Shorts da la API de YouTube Analytics (15/10/2026).
Lo lanza a mano el workflow "Probar analytics"."""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

c = Credentials.from_authorized_user_file(str(Path(__file__).resolve().parent.parent / "token.json"))
if not c.valid:
    c.refresh(Request())
ya = build("youtubeAnalytics", "v2", credentials=c)
for m in ["views,averageViewPercentage", "views,engagedViews", "views,viewedVsSwipedAway",
          "views,shortsViewedVsSwipedAway", "views,averageViewDuration"]:
    try:
        r = ya.reports().query(ids="channel==MINE", startDate="2026-10-01", endDate="2026-10-14",
                               metrics=m, dimensions="video", sort="-views", maxResults=3).execute()
        print("OK", m, [h["name"] for h in r["columnHeaders"]], r.get("rows", [])[:3])
    except Exception as e:
        print("NO", m, str(e)[:200])
