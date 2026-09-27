"""
Busca y descarga imágenes REALES de dominio público / libres de Wikimedia Commons,
gratis y sin API key. Útil para cualquier tema (historia, animales, cultura, etc.),
a diferencia del catálogo de la NASA que solo cubre espacio/ciencia.

Uso:
    python buscar_imagenes_wikimedia.py "consultas.txt" carpeta_salida/
"""
import re
import sys
import time
import requests
from pathlib import Path

API_URL = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "CanalIA-SabiasQue/1.0 (educational content pipeline)"}


PALABRAS_VACIAS = {
    "photo", "photograph", "picture", "image", "close", "up", "closeup", "view",
    "shot", "scene", "real", "aerial", "satellite", "illustration", "the", "and",
    "of", "in", "on", "a", "an", "era",
}


def _palabras_clave(query: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z]+", query.lower()) if len(w) > 3 and w not in PALABRAS_VACIAS}


def _nombre_propio(query: str) -> list[str] | None:
    """Si la consulta parece contener un nombre y apellido propios (dos palabras
    seguidas que empiezan en mayúscula, p.ej. 'Stanislav Petrov'), los devuelve en
    minúscula. Sirve para exigir coincidencia de AMBAS palabras y evitar confundir
    a la persona buscada con un homónimo (ver aprendizajes.md, short_012)."""
    m = re.search(r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)\b", query)
    if not m:
        return None
    return [m.group(1).lower(), m.group(2).lower()]


def _es_relevante(titulo: str, palabras_clave: set[str], query: str) -> bool:
    titulo_normalizado = titulo.lower()
    nombre = _nombre_propio(query)
    if nombre:
        return all(parte in titulo_normalizado for parte in nombre)
    if not palabras_clave:
        return True
    return any(palabra in titulo_normalizado for palabra in palabras_clave)


def buscar_archivo(query: str, intentos: int = 4, excluir: set | None = None) -> str | None:
    """excluir: URLs ya usadas en el vídeo. Se saltan y la elegida se añade, para no
    repetir la misma foto con búsquedas distintas (pasaba mucho: devuelve la más grande)."""
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,  # namespace File:
        "gsrsearch": f"{query} filetype:bitmap",
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "iiurlwidth": 1600,
    }
    data = None
    for intento in range(1, intentos + 1):
        resp = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        if resp.status_code == 429:
            time.sleep(intento * 8)
            continue
        resp.raise_for_status()
        data = resp.json()
        break
    if data is None:
        raise requests.exceptions.RequestException(f"429 persistente para: {query}")
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None

    palabras_clave = _palabras_clave(query)
    candidatos = []
    candidatos_irrelevantes = []
    for page in pages.values():
        infos = page.get("imageinfo", [])
        if not infos:
            continue
        info = infos[0]
        mime = info.get("mime", "")
        if "svg" in mime or "gif" in mime:
            continue
        ancho = info.get("width", 0)
        if ancho < 800:
            continue
        url = info.get("thumburl") or info.get("url")
        titulo = page.get("title", "")
        # Se comprueba SOLO el título (no categorías: se probó ampliar a categorías
        # y volvió a colar falsos positivos graves, como una foto de una audiencia
        # cualquiera en un evento de Putin para la búsqueda "Stanislav Petrov photo",
        # solo por coincidencia de categoría genérica). Es preferible rechazar de más
        # -y caer al respaldo IA- que mostrar con confianza una foto real pero
        # equivocada. Ver aprendizajes.md.
        if _es_relevante(titulo, palabras_clave, query):
            candidatos.append((ancho, url))
        else:
            candidatos_irrelevantes.append((ancho, url, titulo))

    if excluir is not None:
        candidatos = [c for c in candidatos if c[1] not in excluir]
    if candidatos:
        candidatos.sort(reverse=True)
        if excluir is not None:
            excluir.add(candidatos[0][1])
        return candidatos[0][1]
    if candidatos_irrelevantes:
        # Ningún resultado tiene el título relacionado con la búsqueda: es mejor no
        # usar una foto real pero equivocada (ver aprendizajes.md, short_012: una
        # búsqueda de un nombre propio devolvió la foto de un futbolista homónimo,
        # y otra búsqueda devolvió un pez de arrecife) que caer en el respaldo IA.
        print(f"  descartados {len(candidatos_irrelevantes)} resultado(s) sin relación con '{query}' "
              f"(ej. título: '{candidatos_irrelevantes[0][2]}')")
    return None


def descargar(url: str, salida: Path, intentos: int = 3):
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            salida.write_bytes(resp.content)
            return
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            time.sleep(intento * 3)
    raise ultimo_error


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python buscar_imagenes_wikimedia.py <consultas.txt> <carpeta_salida>")
        sys.exit(1)

    consultas_path = Path(sys.argv[1])
    carpeta_salida = Path(sys.argv[2])
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    consultas = [l.strip() for l in consultas_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    for i, query in enumerate(consultas, start=1):
        salida = carpeta_salida / f"wiki_{i:02d}.jpg"
        if salida.exists():
            print(f"Ya existe, se omite: {salida}")
            continue
        try:
            url = buscar_archivo(query)
            if not url:
                print(f"[{i}] Sin resultados para: {query}")
                continue
            descargar(url, salida)
            print(f"[{i}] '{query}' -> {salida.name}")
        except requests.exceptions.RequestException as e:
            print(f"[{i}] ERROR con '{query}': {e}")
        time.sleep(2.5)
