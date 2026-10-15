"""
Títulos y descripciones traducidos (inglés y portugués) en cada vídeo
(15/10/2026). YouTube muestra la traducción a quien tiene el idioma de su
cuenta en inglés o portugués, en el feed y en la búsqueda: más alcance sin
tocar el vídeo.

- Traduce con Gemini (gratis) los vídeos públicos que aún no tengan
  localizaciones y las guarda con videos.update (50 unidades de cuota cada uno).
- Máximo por ejecución para no comerse la cuota diaria.

Lo lanza .github/workflows/localizar.yml una vez al día, justo después del
reinicio de cuota.

Uso:
    python scripts/localizar.py [max_videos]
"""
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent))
import gemini  # noqa: E402

BASE = Path(__file__).resolve().parent.parent
IDIOMAS = {"en": "inglés (de Estados Unidos)", "pt": "portugués de Brasil"}

SISTEMA = (
    "Eres el editor de un canal de YouTube Shorts de curiosidades. Traduces el título y la "
    "descripción de un Short del español a {idioma}. El título debe sonar nativo y "
    "enganchar igual que el original (no lo hagas más largo, máximo 70 caracteres, sin "
    "comillas) y NO debe revelar el animal, lugar o persona si el original no lo revela. "
    "En la descripción traduce el texto y conserva los hashtags traducidos, #shorts y "
    "cualquier línea de créditos o licencias tal cual. No añadas nada."
)
ESQUEMA = {"type": "OBJECT", "properties": {"titulo": {"type": "STRING"},
                                            "descripcion": {"type": "STRING"}},
           "required": ["titulo", "descripcion"]}


def youtube():
    cred = Credentials.from_authorized_user_file(str(BASE / "token.json"))
    if not cred.valid:
        cred.refresh(Request())
    return build("youtube", "v3", credentials=cred)


def ids_publicos(yt) -> list[str]:
    subidas = yt.channels().list(part="contentDetails", mine=True).execute()[
        "items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails,status", playlistId=subidas,
                                    maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]
                if i["status"]["privacyStatus"] == "public"]
        token = r.get("nextPageToken")
        if not token:
            return ids


def main(maximo: int):
    yt = youtube()
    ids = ids_publicos(yt)
    hechos = 0
    for i in range(0, len(ids), 50):
        if hechos >= maximo:
            break
        lote = yt.videos().list(part="snippet,localizations", id=",".join(ids[i:i + 50])).execute()
        for v in lote["items"]:
            if hechos >= maximo:
                break
            locs = v.get("localizations", {})
            if all(l in locs for l in IDIOMAS):
                continue
            sn = v["snippet"]
            for lang, nombre in IDIOMAS.items():
                if lang in locs:
                    continue
                t = gemini.json_estructurado(
                    SISTEMA.format(idioma=nombre),
                    [{"text": f"TÍTULO:\n{sn['title']}\n\nDESCRIPCIÓN:\n{sn.get('description', '')}"}],
                    ESQUEMA)
                if not t or not t["titulo"].strip():
                    break
                locs[lang] = {"title": t["titulo"].strip()[:100],
                              "description": t["descripcion"].strip()[:5000]}
            else:
                cuerpo = {"id": v["id"], "localizations": locs, "snippet": {
                    "title": sn["title"], "description": sn.get("description", ""),
                    "categoryId": sn["categoryId"], "tags": sn.get("tags", []),
                    "defaultLanguage": sn.get("defaultLanguage") or "es"}}
                yt.videos().update(part="snippet,localizations", body=cuerpo).execute()
                hechos += 1
                print(f"  ok {v['id']}: {sn['title']} -> {locs['en']['title']}")
    print(f"Localizados {hechos} vídeos.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 40)
