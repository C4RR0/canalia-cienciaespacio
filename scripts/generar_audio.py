"""
Genera un audio narrado en español a partir de un guion de texto usando edge-tts (gratis, sin API key).

Uso:
    python generar_audio.py guiones/mi_guion.txt audio/mi_guion.mp3 [voz]

Voces recomendadas en español (prueba varias y elige la que más encaje con el canal):
    es-ES-AlvaroNeural   -> hombre, España, tono serio/narrativo
    es-ES-ElviraNeural   -> mujer, España, tono claro/neutro
    es-MX-JorgeNeural    -> hombre, México, tono cercano
    es-MX-DaliaNeural    -> mujer, México, tono cercano
"""
import sys
import asyncio
import edge_tts

VOZ_POR_DEFECTO = "es-ES-AlvaroNeural"


async def generar(texto_path: str, salida_path: str, voz: str):
    with open(texto_path, "r", encoding="utf-8") as f:
        texto = f.read().strip()

    if not texto:
        raise ValueError("El guion está vacío.")

    comunicador = edge_tts.Communicate(texto, voz, rate="+0%", pitch="+0Hz")
    await comunicador.save(salida_path)
    print(f"Audio generado: {salida_path} (voz: {voz})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python generar_audio.py <guion.txt> <salida.mp3> [voz]")
        sys.exit(1)

    guion = sys.argv[1]
    salida = sys.argv[2]
    voz = sys.argv[3] if len(sys.argv) > 3 else VOZ_POR_DEFECTO

    asyncio.run(generar(guion, salida, voz))
