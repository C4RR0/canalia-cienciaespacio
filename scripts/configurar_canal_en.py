"""Descripción, palabras clave e idioma del canal en inglés (Wild Facts Daily).
Se ejecuta a mano con el workflow "Configurar canal inglés" (usa token_en.json)."""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parent.parent
cred = Credentials.from_authorized_user_file(str(BASE / "token_en.json"))
if not cred.valid:
    cred.refresh(Request())
yt = build("youtube", "v3", credentials=cred)
ch = yt.channels().list(part="brandingSettings,snippet", mine=True).execute()["items"][0]
print("Canal:", ch["snippet"]["title"])
b = ch["brandingSettings"]
b["channel"]["description"] = (
    "Brutal animals, forbidden places and true stories that sound made up. "
    "New wild facts every day, in under a minute.\n\n"
    "Real facts, real images, no filler: the animal that eats a cobra, the town that has been "
    "burning underground since 1962, the man struck by lightning seven times.\n\n"
    "New Shorts every day. If you love learning what nobody told you, subscribe.")
b["channel"]["keywords"] = ('"wild facts" "animal facts" "did you know" "fun facts" "weird animals" '
                            '"amazing animals" "true stories" "strange places" nature mysteries "facts"')
b["channel"]["defaultLanguage"] = "en"
b["channel"]["country"] = "US"
r = yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": b}).execute()
print(r["brandingSettings"]["channel"]["description"])

# Banner y marca de agua de suscripción (branding/, generados con scripts/branding_en.py).
from googleapiclient.http import MediaFileUpload  # noqa: E402

subida = yt.channelBanners().insert(
    media_body=MediaFileUpload(str(BASE / "branding" / "en_banner.png"), mimetype="image/png")).execute()
b = yt.channels().list(part="brandingSettings", mine=True).execute()["items"][0]["brandingSettings"]
b.setdefault("image", {})["bannerExternalUrl"] = subida["url"]
yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": b}).execute()
print("Banner puesto")
yt.watermarks().set(
    channelId=ch["id"],
    body={"timing": {"type": "offsetFromEnd", "offsetMs": 15000}, "position": {
        "type": "corner", "cornerPosition": "topRight"}},
    media_body=MediaFileUpload(str(BASE / "branding" / "en_marca_agua.png"), mimetype="image/png")).execute()
print("Marca de agua de suscripción puesta")
