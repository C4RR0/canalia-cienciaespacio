"""Descripción, palabras clave, idioma, banner y marca de agua del canal en inglés
(Wild Facts Daily). Se ejecuta a mano con el workflow "Configurar canal inglés"
(usa token_en.json). Imágenes en branding/, generadas con scripts/branding_en.py.

Uso:
    python scripts/configurar_canal_en.py               # todo
    python scripts/configurar_canal_en.py --solo-marca  # solo la marca de agua
"""
import json
import sys
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE = Path(__file__).resolve().parent.parent
CRLF = "\r\n"

cred = Credentials.from_authorized_user_file(str(BASE / "token_en.json"))
if not cred.valid:
    cred.refresh(Request())
yt = build("youtube", "v3", credentials=cred)
ch = yt.channels().list(part="brandingSettings,snippet", mine=True).execute()["items"][0]
print("Canal:", ch["snippet"]["title"])

if "--solo-marca" not in sys.argv:
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
    subida = yt.channelBanners().insert(
        media_body=MediaFileUpload(str(BASE / "branding" / "en_banner.png"), mimetype="image/png")).execute()
    b.setdefault("image", {})["bannerExternalUrl"] = subida["url"]
    yt.channels().update(part="brandingSettings", body={"id": ch["id"], "brandingSettings": b}).execute()
    print("Descripción, palabras clave y banner puestos")

# watermarks.set con la librería falla al leer la respuesta vacía ("range() arg 3 must
# not be zero"): se hace a mano, multipart.
meta = {"timing": {"type": "offsetFromEnd", "offsetMs": 15000},
        "position": {"type": "corner", "cornerPosition": "topRight"}}
img = (BASE / "branding" / "en_marca_agua.png").read_bytes()
frontera = "frontera_marca_agua"
cuerpo = (f"--{frontera}{CRLF}Content-Type: application/json; charset=UTF-8{CRLF}{CRLF}"
          f"{json.dumps(meta)}{CRLF}--{frontera}{CRLF}Content-Type: image/png{CRLF}{CRLF}").encode() \
    + img + f"{CRLF}--{frontera}--".encode()
r = requests.post("https://www.googleapis.com/upload/youtube/v3/watermarks/set",
                  params={"channelId": ch["id"], "uploadType": "multipart"}, data=cuerpo,
                  headers={"Authorization": f"Bearer {cred.token}",
                           "Content-Type": f"multipart/related; boundary={frontera}"}, timeout=60)
print("watermarks.set ->", r.status_code, r.text[:300])
r.raise_for_status()
print("Marca de agua de suscripción puesta")
