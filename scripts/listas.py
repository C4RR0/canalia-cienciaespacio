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
import re
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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

# Series (3/11/2026, tarea de Vera en la oficina): listas EXTRA para encadenar visionados de una serie. Un Short
# puede estar a la vez en su lista temática y en su serie. Entra en la serie el Short cuyo config casa con la
# expresión, salvo los de NO_SERIE; además se añade al final de su descripción el enlace a la lista de la serie.
SERIES = {
    "parasitos": ("Parásitos que controlan a sus víctimas",
                  "Avispas que convierten cucarachas en zombis, hongos que deciden dónde muere una hormiga, gusanos "
                  "que obligan a un grillo a tirarse al agua… La serie completa de parásitos del canal, con datos "
                  "reales en menos de un minuto.",
                  r"par[aá]sit|zombi|hu[eé]sped",
                  {"short_154_pez_loro_moco", "short_243_indicador_miel", "short_261_pez_limpiador_espejo",
                   "short_286_rabihorcado"},
                  "▶️ Toda la serie de parásitos, seguida: https://www.youtube.com/playlist?list={}"),
    # 4/11/2026: segundo tema que más rinde (lugares, 1.783 de media). "titulo:" = la expresión se busca solo en
    # el título del config (en el texto entero casaría con cualquier guion que diga «pueblo» o «isla»).
    "lugares": ("Lugares imposibles que existen de verdad",
                "Pueblos que arden bajo tierra, lagos que convierten animales en piedra, islas donde está "
                "prohibido desembarcar… Todos los lugares insólitos del canal, seguidos y en menos de un minuto.",
                r"titulo:^(El|La|Esta|Este) (pueblo|aldea|isla|ciudad|lago|templo|capital|cueva|volcán|faro|bosque|"
                r"desierto|mina|valle|país|playa|río|cementerio|carretera|montaña|calle|casa|hotel|cráter|puerto|"
                r"torre|catedral|santuario|iglesia)\b",
                set(),
                "▶️ Más lugares imposibles, seguidos: https://www.youtube.com/playlist?list={}"),
}


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
    series(yt, estado, videos, maximo)


def titulos_de_serie(patron: str, fuera: set) -> set:
    titulos = set()
    for ruta in glob.glob(str(BASE / "produccion_config" / "short_*.json")):
        if Path(ruta).stem in fuera:
            continue
        texto = Path(ruta).read_text(encoding="utf-8")
        titulo = (json.loads(texto).get("titulo") or "").strip()
        if patron.startswith("titulo:"):
            casa = re.search(patron[len("titulo:"):], titulo, re.I)
        else:
            casa = re.search(patron, texto, re.I)
        if casa and titulo:
            titulos.add(titulo)
    return titulos


def series(yt, estado, videos: dict, maximo: int):
    """Crea las listas de SERIES, mete sus Shorts y pone el enlace a la serie en la descripción de cada uno."""
    ids = estado.setdefault("series", {})
    for clave, (titulo, descripcion, patron, fuera, enlace) in SERIES.items():
        # Cada serie lleva su propio registro de descripciones ya enlazadas (la de parásitos conserva el nombre antiguo)
        campo = "con_enlace_serie" if clave == "parasitos" else f"con_enlace_serie_{clave}"
        con_enlace = set(estado.setdefault(campo, []))
        if not ids.get(clave):
            r = yt.playlists().insert(part="snippet,status", body={
                "snippet": {"title": titulo, "description": descripcion, "defaultLanguage": "es"},
                "status": {"privacyStatus": "public"}}).execute()
            ids[clave] = r["id"]
            print(f"Serie creada: {titulo} ({r['id']})")
            ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        pid = ids[clave]
        dentro, token = set(), None
        while True:
            # Una lista recién creada puede tardar en aparecer para la API (404 playlistNotFound, 4/11/2026)
            for intento in range(6):
                try:
                    r = yt.playlistItems().list(part="contentDetails", playlistId=pid, maxResults=50,
                                                pageToken=token).execute()
                    break
                except HttpError as e:
                    if e.resp.status != 404 or intento == 5:
                        raise
                    time.sleep(20)
            dentro |= {i["contentDetails"]["videoId"] for i in r["items"]}
            token = r.get("nextPageToken")
            if not token:
                break
        suyos = titulos_de_serie(patron, fuera)
        miembros = [vid for vid, (_, dur, t) in videos.items() if t.strip() in suyos and dur <= 70]
        nuevos = [v for v in miembros if v not in dentro][:maximo]
        for vid in nuevos:
            yt.playlistItems().insert(part="snippet", body={"snippet": {
                "playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": vid}}}).execute()
            print(f"  + serie {clave}: {videos[vid][2]}")
        # Enlace en la descripción (videos.update = 50 unidades: como mucho `maximo` por ejecución)
        linea = enlace.format(pid)
        hechos = 0
        for vid in miembros:
            if vid in con_enlace or hechos >= maximo:
                continue
            v = yt.videos().list(part="snippet", id=vid).execute()["items"]
            if not v:
                continue
            sn = v[0]["snippet"]
            if linea not in sn.get("description", ""):
                cuerpo = {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage") if k in sn}
                cuerpo["description"] = (sn.get("description", "").rstrip() + "\n\n" + linea).strip()
                yt.videos().update(part="snippet", body={"id": vid, "snippet": cuerpo}).execute()
                hechos += 1
            con_enlace.add(vid)
        estado[campo] = sorted(con_enlace)
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Serie {clave}: {len(miembros)} Shorts, {len(nuevos)} añadidos, {hechos} descripciones con enlace.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
