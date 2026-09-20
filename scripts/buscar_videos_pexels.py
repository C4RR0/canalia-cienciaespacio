"""
Busca y descarga clips de vídeo REAL (no fotos) de Pexels Videos, gratis con
una API key gratuita (sin tarjeta de crédito). Se usa para el sub-formato
"lista horizontal" tipo XpressTV (25 cosas que no sabías, con vídeo real de
fondo en vez de diapositivas estáticas).

Cómo conseguir la API key (gratis, ~2 minutos):
    1. Entra en https://www.pexels.com/api/ y crea una cuenta gratuita.
    2. Te dan una API key al momento, sin necesidad de tarjeta.
    3. Guárdala en un archivo "pexels_api_key.txt" en la raíz del proyecto
       (junto a client_secret.json), o pásala por variable de entorno
       PEXELS_API_KEY.

Uso:
    python buscar_videos_pexels.py "consultas.txt" carpeta_salida/ [orientacion]

orientacion: "landscape" (defecto, para el formato horizontal) o "portrait"
consultas.txt: una consulta de búsqueda por línea (en inglés funciona mejor).
Cada línea descarga el mejor clip disponible (más cercano a 1920x1080,
calidad "hd", duración entre 4 y 20 segundos para que no sea ni un parpadeo
ni un clip absurdamente largo).
"""
import os
import re
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from buscar_imagenes_wikimedia import _palabras_clave, _nombre_propio

BASE = Path(__file__).parent.parent
API_URL = "https://api.pexels.com/videos/search"
DUR_MIN, DUR_MAX = 4, 20


def cargar_api_key() -> str:
    env = os.environ.get("PEXELS_API_KEY")
    if env:
        return env.strip()
    key_path = BASE / "pexels_api_key.txt"
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        "No se encontró la API key de Pexels. Consigue una gratis en "
        "https://www.pexels.com/api/ y guárdala en pexels_api_key.txt "
        "(en la raíz del proyecto) o en la variable de entorno PEXELS_API_KEY."
    )


def _es_relevante_pexels(video: dict, palabras_clave: set[str], query: str) -> bool:
    # Pexels no da título/descripción por vídeo, solo etiquetas ("tags") en
    # algunas respuestas y el propio "url" (que suele incluir palabras
    # descriptivas del contenido, p.ej. .../video/a-red-panda-eating-bamboo-.../).
    # Se usa esa URL como señal de relevancia, con la misma lógica ya probada
    # en Wikimedia/NASA (ver aprendizajes.md): mejor rechazar de más que
    # arriesgar un clip totalmente ajeno al tema.
    texto = video.get("url", "").lower().replace("-", " ")
    nombre = _nombre_propio(query)
    if nombre:
        return all(parte in texto for parte in nombre)
    if not palabras_clave:
        return True
    return any(palabra in texto for palabra in palabras_clave)


def buscar_mejor_clip(query: str, api_key: str, orientacion: str = "landscape") -> dict | None:
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 12, "orientation": orientacion}
    resp = requests.get(API_URL, params=params, headers=headers, timeout=30)
    if resp.status_code == 429:
        raise requests.exceptions.RequestException("Límite de peticiones de Pexels alcanzado (rate limit).")
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        return None

    palabras_clave = _palabras_clave(query)
    for video in videos:
        duracion = video.get("duration", 0)
        if not (DUR_MIN <= duracion <= DUR_MAX):
            continue
        if not _es_relevante_pexels(video, palabras_clave, query):
            continue
        return video
    return None


def obtener_url_archivo(video: dict, orientacion: str) -> str | None:
    archivos = video.get("video_files", [])
    # Prioriza calidad "hd" (1280x720 o similar) para no descargar 4K innecesario
    candidatos_hd = [f for f in archivos if f.get("quality") == "hd" and f.get("file_type") == "video/mp4"]
    candidatos = candidatos_hd or [f for f in archivos if f.get("file_type") == "video/mp4"]
    if not candidatos:
        return None
    # entre los "hd", el más cercano a 1280 de ancho (evita el más pesado innecesariamente)
    candidatos.sort(key=lambda f: abs((f.get("width") or 1280) - 1280))
    return candidatos[0].get("link")


def descargar(url: str, salida: Path, intentos: int = 3):
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            resp = requests.get(url, timeout=120, stream=True)
            resp.raise_for_status()
            with open(salida, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    f.write(chunk)
            return
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            time.sleep(intento * 3)
    raise ultimo_error


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python buscar_videos_pexels.py <consultas.txt> <carpeta_salida> [orientacion: landscape|portrait]")
        sys.exit(1)

    consultas_path = Path(sys.argv[1])
    carpeta_salida = Path(sys.argv[2])
    orientacion = sys.argv[3] if len(sys.argv) > 3 else "landscape"
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    api_key = cargar_api_key()
    consultas = [l.strip() for l in consultas_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    for i, query in enumerate(consultas, start=1):
        salida = carpeta_salida / f"clip_{i:02d}.mp4"
        if salida.exists():
            print(f"Ya existe, se omite: {salida}")
            continue
        try:
            video = buscar_mejor_clip(query, api_key, orientacion)
            if not video:
                print(f"[{i}] Sin clip relevante para: {query}")
                continue
            url = obtener_url_archivo(video, orientacion)
            if not url:
                print(f"[{i}] Sin archivo descargable para: {query}")
                continue
            descargar(url, salida)
            print(f"[{i}] '{query}' -> {salida.name} ({video.get('duration')}s)")
        except requests.exceptions.RequestException as e:
            print(f"[{i}] ERROR con '{query}': {e}")
        time.sleep(1)
