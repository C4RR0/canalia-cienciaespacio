"""
Genera imágenes con IA a partir de una lista de prompts, usando Pollinations.ai (gratis, sin API key).

Uso:
    python generar_imagenes.py prompts.txt carpeta_salida/ [ancho] [alto]

prompts.txt: un prompt por línea (en inglés funciona mejor con el modelo).
Formato horizontal (vídeos largos): 1792x1024
Formato vertical (shorts):          1024x1792
"""
import sys
import time
import urllib.parse
import requests
from pathlib import Path

BASE_URL = "https://image.pollinations.ai/prompt/{prompt}"


def generar_imagen(prompt: str, ancho: int, alto: int, salida: Path, semilla: int, intentos: int = 4):
    prompt_codificado = urllib.parse.quote(prompt)
    url = BASE_URL.format(prompt=prompt_codificado)
    params = {
        "width": ancho,
        "height": alto,
        "seed": semilla,
        "nologo": "true",
        "model": "flux",
    }
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            resp = requests.get(url, params=params, timeout=120)
            resp.raise_for_status()
            salida.write_bytes(resp.content)
            print(f"Imagen guardada: {salida}")
            return
        except requests.exceptions.RequestException as e:
            ultimo_error = e
            espera = intento * 5
            print(f"  intento {intento}/{intentos} fallido ({e}), reintentando en {espera}s...")
            time.sleep(espera)
    raise ultimo_error


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python generar_imagenes.py <prompts.txt> <carpeta_salida> [ancho] [alto]")
        sys.exit(1)

    prompts_path = Path(sys.argv[1])
    carpeta_salida = Path(sys.argv[2])
    ancho = int(sys.argv[3]) if len(sys.argv) > 3 else 1792
    alto = int(sys.argv[4]) if len(sys.argv) > 4 else 1024

    carpeta_salida.mkdir(parents=True, exist_ok=True)
    prompts = [l.strip() for l in prompts_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    for i, prompt in enumerate(prompts, start=1):
        salida = carpeta_salida / f"img_{i:02d}.jpg"
        if salida.exists():
            print(f"Ya existe, se omite: {salida}")
            continue
        generar_imagen(prompt, ancho, alto, salida, semilla=i * 1000 + 7)
        time.sleep(1)  # cortesía con el servicio gratuito
