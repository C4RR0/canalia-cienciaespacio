"""
Buzón de órdenes para el canal (19/10/2026). Los agentes de la oficina virtual (turno en la nube, sin acceso a
la cuenta de YouTube) dejan órdenes en ordenes/pendientes/<id>.json; el workflow ordenes.yml, que sí tiene el
token del canal, las ejecuta con esta lista cerrada de acciones y deja el resultado en ordenes/hechas/<id>.json.

Formato de una orden:
    {"accion": "lista_crear", "parametros": {...}, "agente": "vera", "tarea": "<id de la tarea del panel>",
     "ok_de_sergio": true, "motivo": "por qué"}

Acciones (todo lo que se ve en el canal exige "ok_de_sergio": true; si no, la orden se rechaza sin tocar nada):
    comprobar           {}                                         solo lee: listas del canal (para probar el buzón)
    lista_crear         {"titulo", "descripcion", "videos": [ids]} lista pública con esos vídeos, en ese orden
    lista_anadir        {"lista_id", "videos": [ids]}              añade vídeos al final de una lista
    descripcion_anadir  {"texto", "videos": [ids] | "todos", "marca"} añade «texto» al final de la descripción;
                        «marca» (un trozo del texto) evita añadirlo dos veces al mismo vídeo
Máximo 40 vídeos por orden (cada cambio cuesta 50 unidades de la cuota diaria de 10.000).

Uso: python scripts/ordenes.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE = Path(__file__).resolve().parent.parent
PENDIENTES, HECHAS = BASE / "ordenes" / "pendientes", BASE / "ordenes" / "hechas"
MAX_VIDEOS = 40
PUBLICAS = {"lista_crear", "lista_anadir", "descripcion_anadir"}


def youtube():
    cred = Credentials.from_authorized_user_file(str(BASE / "token.json"))
    if not cred.valid:
        cred.refresh(Request())
    return build("youtube", "v3", credentials=cred)


def ids_de(p, yt):
    videos = p.get("videos") or []
    if videos == "todos":
        canal = yt.channels().list(part="contentDetails", mine=True).execute()["items"][0]
        subidas, videos, token = canal["contentDetails"]["relatedPlaylists"]["uploads"], [], None
        while True:
            r = yt.playlistItems().list(part="contentDetails", playlistId=subidas, maxResults=50, pageToken=token).execute()
            videos += [i["contentDetails"]["videoId"] for i in r["items"]]
            token = r.get("nextPageToken")
            if not token:
                break
    if not isinstance(videos, list) or not all(isinstance(v, str) and len(v) == 11 for v in videos):
        raise ValueError("«videos» tiene que ser una lista de ids de YouTube (11 caracteres) o \"todos\"")
    return videos


def comprobar(yt, p):
    r = yt.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50).execute()
    return "Listas del canal: " + "; ".join(f"{i['snippet']['title']} ({i['id']}, {i['contentDetails']['itemCount']} vídeos)"
                                            for i in r["items"])


def lista_crear(yt, p):
    videos = ids_de(p, yt)[:MAX_VIDEOS]
    r = yt.playlists().insert(part="snippet,status", body={
        "snippet": {"title": str(p["titulo"])[:150], "description": str(p.get("descripcion", ""))[:5000], "defaultLanguage": "es"},
        "status": {"privacyStatus": "public"}}).execute()
    for v in videos:
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": r["id"], "resourceId": {"kind": "youtube#video", "videoId": v}}}).execute()
    return f"Lista «{p['titulo']}» creada ({r['id']}) con {len(videos)} vídeos."


def lista_anadir(yt, p):
    videos = ids_de(p, yt)[:MAX_VIDEOS]
    for v in videos:
        yt.playlistItems().insert(part="snippet", body={"snippet": {
            "playlistId": p["lista_id"], "resourceId": {"kind": "youtube#video", "videoId": v}}}).execute()
    return f"{len(videos)} vídeos añadidos a la lista {p['lista_id']}."


def descripcion_anadir(yt, p):
    texto, marca = str(p["texto"]).strip(), str(p.get("marca") or p["texto"]).strip()[:60]
    if not texto:
        raise ValueError("«texto» vacío")
    videos, cambiados, ya = ids_de(p, yt), 0, 0
    for i in range(0, len(videos), 50):
        for item in yt.videos().list(part="snippet", id=",".join(videos[i:i + 50])).execute()["items"]:
            sn = item["snippet"]
            if marca in sn.get("description", ""):
                ya += 1
                continue
            if cambiados >= MAX_VIDEOS:
                break
            cuerpo = {k: sn[k] for k in ("title", "categoryId", "tags", "defaultLanguage") if k in sn}
            cuerpo["description"] = (sn.get("description", "").rstrip() + "\n\n" + texto)[:5000]
            yt.videos().update(part="snippet", body={"id": item["id"], "snippet": cuerpo}).execute()
            cambiados += 1
    return f"Texto añadido a {cambiados} vídeos ({ya} ya lo tenían)."


ACCIONES = {"comprobar": comprobar, "lista_crear": lista_crear, "lista_anadir": lista_anadir,
            "descripcion_anadir": descripcion_anadir}


def main():
    ordenes = sorted(PENDIENTES.glob("*.json")) if PENDIENTES.exists() else []
    if not ordenes:
        print("No hay órdenes pendientes.")
        return
    HECHAS.mkdir(parents=True, exist_ok=True)
    yt, fallos = youtube(), 0
    for ruta in ordenes:
        orden = {}
        try:
            orden = json.loads(ruta.read_text(encoding="utf-8"))
            accion = orden.get("accion")
            if accion not in ACCIONES:
                raise ValueError(f"acción desconocida «{accion}» (válidas: {', '.join(ACCIONES)})")
            if accion in PUBLICAS and orden.get("ok_de_sergio") is not True:
                raise PermissionError("se ve en el canal y no lleva ok_de_sergio: true; no se ha tocado nada")
            orden["resultado"], orden["estado"] = ACCIONES[accion](yt, orden.get("parametros") or {}), "hecha"
        except Exception as e:  # una orden mala no frena a las demás
            orden["resultado"], orden["estado"] = f"{type(e).__name__}: {e}", "fallida"
            fallos += 1
        orden["ejecutada"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (HECHAS / ruta.name).write_text(json.dumps(orden, ensure_ascii=False, indent=1), encoding="utf-8")
        ruta.unlink()
        print(f"{ruta.name}: {orden['estado']} · {orden['resultado']}")
    if fallos:
        sys.exit(1)  # el run sale en rojo para que se note


if __name__ == "__main__":
    main()
