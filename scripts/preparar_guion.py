"""
Procesa un guion con marcadores inline [[DATO: texto de la tarjeta]]:
- Genera el texto limpio (sin marcadores) listo para el TTS.
- Genera un archivo de marcadores con la posición relativa (0-1) de cada dato dentro del texto,
  para poder sincronizarlos con el audio final una vez se conozca su duración.

Uso:
    python preparar_guion.py guion_con_marcadores.txt guion_limpio.txt marcadores.txt
"""
import re
import sys
from pathlib import Path

PATRON = re.compile(r"\[\[DATO:\s*(.*?)\s*\]\]")


def procesar(entrada: str, salida_limpio: str, salida_marcadores: str):
    texto = Path(entrada).read_text(encoding="utf-8")

    limpio = []
    marcadores = []
    cursor_limpio = 0
    pos = 0

    for m in PATRON.finditer(texto):
        antes = texto[pos:m.start()]
        limpio.append(antes)
        cursor_limpio += len(antes)
        marcadores.append((cursor_limpio, m.group(1)))
        pos = m.end()

    limpio.append(texto[pos:])
    texto_limpio = "".join(limpio)
    # normaliza espacios dobles que puedan quedar donde estaba el marcador
    texto_limpio = re.sub(r"[ \t]{2,}", " ", texto_limpio)

    total_chars = len(texto_limpio)
    Path(salida_limpio).write_text(texto_limpio.strip(), encoding="utf-8")

    with open(salida_marcadores, "w", encoding="utf-8") as f:
        for offset, dato_texto in marcadores:
            fraccion = offset / total_chars if total_chars else 0
            f.write(f"{fraccion:.6f}|{dato_texto}\n")

    print(f"Guion limpio: {salida_limpio} ({total_chars} caracteres)")
    print(f"Marcadores: {salida_marcadores} ({len(marcadores)} datos)")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python preparar_guion.py <guion_con_marcadores.txt> <guion_limpio.txt> <marcadores.txt>")
        sys.exit(1)

    procesar(sys.argv[1], sys.argv[2], sys.argv[3])
