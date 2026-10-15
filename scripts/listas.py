"""
Listas de reproducción temáticas del canal (15/10/2026: el canal no tenía
ninguna). Quien termina un Short y ve "lista" sigue viendo más del canal, y
las listas también salen en búsqueda.

- Crea las listas de LISTAS si no existen (ids guardados en listas.json).
- Añade a su lista cada Short público (<= 70 s) que aún no esté, de más a menos
  visto, con un máximo por ejecución para no quitarle cuota de la API a las
  subidas (cada inserción cuesta 50 unidades).
- Tema de cada vídeo: el de listas.json["temas"] (asignado a mano para los
  antiguos) o, si no está, el tema_visual de su config (buscado por título).

Lo ejecuta metricas.yml una vez al día.

Uso:
    python scripts/listas.py [max_inserciones]
"""
import csv
import glob
import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parent.parent
ESTADO = BASE / "listas.json"

LISTAS = {
    "animales": ("Animales brutales y extraños",
                 "Los animales más raros, crueles y alucinantes del planeta: cómo cazan, "
                 "cómo se defienden y cómo se reproducen. Datos reales en menos de un minuto."),
    "historias": ("Lugares y sucesos insólitos",
                  "Pueblos, lagos, islas y personas con historias que parecen inventadas pero "
                  "son reales. Datos verificados en menos de un minuto."),
    "ciencia": ("Espacio y ciencia que nadie te contó",
                "El universo, la Tierra y la ciencia de cada día con los datos que no te "
                "enseñaron en clase. En menos de un minuto."),
}
# tema_visual de los configs -> lista
POR_TEMA_VISUAL = {"naturaleza": "animales", "historia": "historias", "adulto": "historias",
                   "curiosidades": "historias", "espacio": "ciencia", "ciencia": "ciencia",
                   "familiar": "animales"}


def youtube():
    cred = Credentials.from_authorized_user_file(str(BASE / "token.json"))
    if not cred.valid:
        cred.refresh(Request())
    return build("youtube", "v3", credentials=cred)


def ultima_foto_videos() -> dict:
    """video_id -> (vistas, duracion_s, titulo) de la última fecha de metricas/videos.csv."""
    filas = list(csv.DictReader((BASE / "metricas" / "videos.csv").open(encoding="utf-8")))
    ultima = max(f["fecha"] for f in filas)
    return {f["video_id"]: (int(f["vistas"]), int(float(f["duracion_s"] or 0)), f["titulo"])
            for f in filas if f["fecha"] == ultima}


def tema_por_titulo() -> dict:
    temas = {}
    for ruta in glob.glob(str(BASE / "produccion_config" / "short_*.json")):
        cfg = json.loads(Path(ruta).read_text(encoding="utf-8"))
        if cfg.get("titulo") and cfg.get("tema_visual") in POR_TEMA_VISUAL:
            temas[cfg["titulo"].strip()] = POR_TEMA_VISUAL[cfg["tema_visual"]]
    return temas


def main(maximo: int):
    estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    yt = youtube()

    for clave, (titulo, descripcion) in LISTAS.items():
        if not estado["ids"].get(clave):
            r = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": titulo, "description": descripcion, "defaultLanguage": "es"},
                "status": {"privacyStatus": "public"}}).execute()
            estado["ids"][clave] = r["id"]
            print(f"Lista creada: {titulo} ({r['id']})")
            ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    # Lo que ya hay en cada lista (1 unidad por página).
    dentro = set()
    for pid in estado["ids"].values():
        token = None
        while True:
            r = yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50,
                                        pageToken=token).execute()
            dentro |= {i["contentDetails"]["videoId"] for i in r["items"]}
            token = r.get("nextPageToken")
            if not token:
                break

    videos = ultima_foto_videos()
    por_titulo = tema_por_titulo()
    excluidos = set(estado.get("excluidos", []))
    pendientes = []
    for vid, (vistas, dur, titulo) in videos.items():
        if vid in dentro or vid in excluidos or dur > 70:
            continue
        tema = estado["temas"].get(vid) or por_titulo.get(titulo.strip())
        if tema:
            pendientes.append((vistas, vid, tema, titulo))
        else:
            print(f"  [sin tema] {vid} {titulo}")
    pendientes.sort(reverse=True)

    hechos = 0
    for vistas, vid, tema, titulo in pendientes[:maximo]:
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": estado["ids"][tema],
            "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
        hechos += 1
        print(f"  + {tema}: {titulo} ({vistas} vistas)")
    print(f"Añadidos {hechos}; quedan {len(pendientes) - hechos} por añadir.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
