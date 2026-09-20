"""
Busca y descarga imágenes REALES de dominio público del catálogo NASA (images-api.nasa.gov),
gratis y sin API key. Ideal para contenido educativo de ciencia/espacio con credibilidad real.

Uso:
    python buscar_imagenes_nasa.py "consultas.txt" carpeta_salida/

consultas.txt: una consulta de búsqueda por línea (en inglés funciona mejor, es el catálogo de la NASA).
Cada línea genera una imagen (la mejor resultado de esa búsqueda, en la resolución más alta disponible).
"""
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from buscar_imagenes_wikimedia import _palabras_clave, _nombre_propio

SEARCH_URL = "https://images-api.nasa.gov/search"


def _es_relevante_nasa(titulo: str, descripcion: str, palabras_clave: set[str], query: str) -> bool:
    # Igual que en buscar_imagenes_wikimedia.py: el catálogo de NASA también puede
    # devolver resultados sueltos sin relación real (visto en producción: la
    # búsqueda "solar system planets illustration" devolvió un diagrama del
    # sistema exoplanetario "55 Cancri" para un vídeo sobre Venus). Se comprueba
    # título + descripción (la descripción de NASA suele ser un pie de foto
    # fiable, a diferencia de las categorías de Wikimedia).
    texto = f"{titulo} {descripcion}".lower()
    nombre = _nombre_propio(query)
    if nombre:
        return all(parte in texto for parte in nombre)
    if not palabras_clave:
        return True
    return any(palabra in texto for palabra in palabras_clave)


def buscar_mejor_imagen(query: str) -> dict | None:
    params = {"q": query, "media_type": "image"}
    resp = requests.get(SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    items = resp.json().get("collection", {}).get("items", [])
    if not items:
        return None

    palabras_clave = _palabras_clave(query)
    for item in items[:10]:
        datos = item.get("data", [{}])[0]
        titulo = datos.get("title", "")
        descripcion = datos.get("description", "")
        if _es_relevante_nasa(titulo, descripcion, palabras_clave, query):
            return item
    print(f"  descartados {min(len(items),10)} resultado(s) de NASA sin relación con '{query}' "
          f"(ej. título: '{items[0].get('data',[{}])[0].get('title','')}')")
    return None


def obtener_url_alta_resolucion(item: dict) -> str | None:
    href = item.get("href")
    if not href:
        return None
    resp = requests.get(href, timeout=30)
    resp.raise_for_status()
    archivos = resp.json()
    # Prioriza "orig" > "large" > primer archivo disponible
    for clave in ("orig", "large"):
        for f in archivos:
            if clave in f.lower():
                return f
    return archivos[0] if archivos else None


def descargar(url: str, salida: Path):
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    salida.write_bytes(resp.content)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python buscar_imagenes_nasa.py <consultas.txt> <carpeta_salida>")
        sys.exit(1)

    consultas_path = Path(sys.argv[1])
    carpeta_salida = Path(sys.argv[2])
    carpeta_salida.mkdir(parents=True, exist_ok=True)

    consultas = [l.strip() for l in consultas_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    for i, query in enumerate(consultas, start=1):
        salida = carpeta_salida / f"nasa_{i:02d}.jpg"
        if salida.exists():
            print(f"Ya existe, se omite: {salida}")
            continue
        try:
            item = buscar_mejor_imagen(query)
            if not item:
                print(f"[{i}] Sin resultados para: {query}")
                continue
            titulo = item.get("data", [{}])[0].get("title", "")
            url_img = obtener_url_alta_resolucion(item)
            if not url_img:
                print(f"[{i}] Sin URL de imagen para: {query}")
                continue
            descargar(url_img, salida)
            print(f"[{i}] '{query}' -> {salida.name}  (\"{titulo}\")")
        except requests.exceptions.RequestException as e:
            print(f"[{i}] ERROR con '{query}': {e}")
        time.sleep(0.5)
