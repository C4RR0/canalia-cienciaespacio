"""
Corrige errores típicos de transcripción automática (ASR) en un archivo .srt,
usando una lista de sustituciones. Útil para arreglar nombres propios y términos
técnicos que Whisper suele transcribir mal.

Uso:
    python corregir_subtitulos.py entrada.srt salida.srt [correcciones.txt]

correcciones.txt (opcional): una corrección por línea, formato "texto_erroneo|texto_correcto"
Si no se indica, usa una lista de correcciones genéricas comunes en español.
"""
import re
import sys
from pathlib import Path

CORRECCIONES_GENERICAS = [
    ("Paradógicamente", "Paradójicamente"),
    ("paradógicamente", "paradójicamente"),
    ("espagetización", "espaguetización"),
    ("Espagetización", "Espaguetización"),
    ("un spaghetti", "un espagueti"),
    ("horizonte de, sucesos", "horizonte de sucesos"),
    ("podrían oquear", "podría noquear"),
    (" oquear ", " noquear "),
    ("Chikchulú", "Chicxulub"),
    ("Chichulub", "Chicxulub"),
    ("Chicxulú", "Chicxulub"),
    ("KPG", "K-Pg"),
    ("K PG", "K-Pg"),
    ("huella de actilar", "huella dactilar"),
    ("el que éste?", "el que estés?"),
    ("tiempo debaciado", "tiempo de vaciado"),
    ("tira para el lado que le da la gana", "gira para el lado que le da la gana"),
    ("revista Natura", "revista Nature"),
]


def cargar_correcciones(path: Path | None):
    correcciones = list(CORRECCIONES_GENERICAS)
    if path and path.exists():
        for linea in path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or "|" not in linea:
                continue
            erroneo, correcto = linea.split("|", 1)
            correcciones.append((erroneo, correcto))
    return correcciones


def corregir(entrada: str, salida: str, correcciones_path: Path | None):
    texto = Path(entrada).read_text(encoding="utf-8")
    correcciones = cargar_correcciones(correcciones_path)

    total_reemplazos = 0
    for erroneo, correcto in correcciones:
        n = texto.count(erroneo)
        if n:
            texto = texto.replace(erroneo, correcto)
            total_reemplazos += n
            print(f"  '{erroneo}' -> '{correcto}'  ({n}x)")

    Path(salida).write_text(texto, encoding="utf-8")
    print(f"Total de correcciones aplicadas: {total_reemplazos}")
    print(f"Guardado en: {salida}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python corregir_subtitulos.py <entrada.srt> <salida.srt> [correcciones.txt]")
        sys.exit(1)

    correcciones_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    corregir(sys.argv[1], sys.argv[2], correcciones_path)
