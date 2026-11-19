"""Pone defaultAudioLanguage = "es" (y defaultLanguage = "es") en los vídeos del canal que lo tengan mal.
Los scripts que retocaban vídeos ya subidos (localizar, listas, ordenes, actualizar_youtube) no lo mandaban
y YouTube lo dejaba en en-US (visto el 19/11/2026 en TODOS los vídeos). Solo cambia el snippet: no toca
títulos, descripciones, etiquetas ni traducciones.
Uso: python scripts/arreglar_idioma_audio.py [N]   (N = últimos N vídeos; por defecto 60; cada cambio = 50 de cuota)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from listar_videos import cargar_credenciales
from googleapiclient.discovery import build


def main(n: int) -> None:
    yt = build("youtube", "v3", credentials=cargar_credenciales())
    canal = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
    subidas = canal["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < n:
        r = yt.playlistItems().list(part="contentDetails", playlistId=subidas, maxResults=50, pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r["items"]]
        token = r.get("nextPageToken")
        if not token:
            break
    ids = ids[:n]
    cambiados = 0
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet", id=",".join(ids[i:i + 50])).execute()["items"]:
            sn = v["snippet"]
            if sn.get("defaultAudioLanguage") == "es" and sn.get("defaultLanguage") == "es":
                continue
            cuerpo = {k: sn[k] for k in ("title", "description", "categoryId", "tags") if k in sn}
            cuerpo["defaultLanguage"] = "es"
            cuerpo["defaultAudioLanguage"] = "es"
            yt.videos().update(part="snippet", body={"id": v["id"], "snippet": cuerpo}).execute()
            cambiados += 1
    print(f"Idioma del audio puesto en español en {cambiados} de {len(ids)} vídeos.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
