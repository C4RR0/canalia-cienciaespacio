"""
Genera un audio narrado en español a partir de un guion de texto usando la
API REST oficial de Azure AI Speech (de pago, capa gratis 500k caracteres/mes).

Reemplaza al antiguo cliente edge-tts (no oficial, gratis): edge-tts usaba
aiohttp con un contexto SSL que ignora la CA del proxy de seguridad del
sandbox cloud, así que no podía salir a internet desde ahí (ver
aprendizajes.md 2026-09-20). Esta versión usa `requests`, que sí respeta
las variables de entorno de CA del proxy, así que puede funcionar tanto en
local como (si el proxy permite el dominio de Azure) dentro de un routine
cloud.

Uso:
    python generar_audio.py guiones/mi_guion.txt audio/mi_guion.mp3 [voz]

Requiere azure_speech_key.json en la raíz del proyecto:
    {"key": "...", "region": "northeurope"}

Voces recomendadas en español (mismos nombres que antes con edge-tts, son
voces neuronales reales de Azure):
    es-ES-AlvaroNeural   -> hombre, España, tono serio/narrativo
    es-ES-ElviraNeural   -> mujer, España, tono claro/neutro
    es-ES-XimenaNeural   -> mujer, España, tono dulce/cálido
    es-MX-JorgeNeural    -> hombre, México, tono cercano
    es-MX-DaliaNeural    -> mujer, México, tono cercano
"""
import sys
import json
from pathlib import Path
from xml.sax.saxutils import escape
import requests
import edge_tts
from edge_tts import communicate as _edge_communicate
from edge_tts.constants import TRUSTED_CLIENT_TOKEN

# 2026-10-13: Microsoft movió la síntesis de speech.platform.bing.com (403
# desde el 10/10) a api.msedgeservices.com; edge-tts 7.2.8 aún usa la URL
# vieja (rany2/edge-tts#490). Hay que pisar la de communicate, no la de
# constants. Quitar cuando salga una versión que lo arregle.
_edge_communicate.WSS_URL = (
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
    f"?Ocp-Apim-Subscription-Key={TRUSTED_CLIENT_TOKEN}"
)

VOZ_POR_DEFECTO = "es-ES-AlvaroNeural"

BASE = Path(__file__).resolve().parent.parent
CREDENCIALES_PATH = BASE / "azure_speech_key.json"


def cargar_credenciales() -> tuple[str, str]:
    if not CREDENCIALES_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró {CREDENCIALES_PATH}. Crea un recurso 'Speech' en "
            "Azure y guarda su clave así: "
            '{"key": "TU_KEY", "region": "tu-region"}'
        )
    datos = json.loads(CREDENCIALES_PATH.read_text(encoding="utf-8"))
    return datos["key"], datos["region"]


def _generar_azure(texto: str, salida_path: str, voz: str):
    key, region = cargar_credenciales()
    ssml = (
        "<speak version='1.0' xml:lang='es-ES'>"
        f"<voice name='{voz}'>{escape(texto)}</voice>"
        "</speak>"
    )
    respuesta = requests.post(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-96kbitrate-mono-mp3",
            "User-Agent": "canalia-cienciaespacio",
        },
        data=ssml.encode("utf-8"),
        timeout=60,
    )
    if respuesta.status_code != 200:
        raise RuntimeError(
            f"Azure Speech devolvió {respuesta.status_code}: {respuesta.text[:500]}"
        )
    Path(salida_path).write_bytes(respuesta.content)


async def _generar_edge_tts(texto: str, salida_path: str, voz: str):
    import asyncio
    from aiohttp import ClientResponseError
    from edge_tts.exceptions import NoAudioReceived

    # El endpoint nuevo da 429 con ráfagas, y a veces corta sin mandar audio
    # (NoAudioReceived, 15/10): reintentar con espera. 15/10 13:59 UTC: 4 intentos
    # en 30 s no bastaron en Actions → espera creciente de hasta ~6 min en total.
    esperas = [20, 40, 60, 90, 150]
    for intento in range(len(esperas) + 1):
        try:
            comunicador = edge_tts.Communicate(texto, voz, rate="+0%", pitch="+0Hz")
            await comunicador.save(salida_path)
            return
        except (ClientResponseError, NoAudioReceived) as e:
            if (isinstance(e, ClientResponseError) and e.status != 429) or intento == len(esperas):
                raise
            print(f"  edge-tts: {type(e).__name__} {getattr(e, 'status', '')}, reintento en {esperas[intento]} s")
            await asyncio.sleep(esperas[intento])


async def generar(texto_path: str, salida_path: str, voz: str):
    with open(texto_path, "r", encoding="utf-8") as f:
        texto = f.read().strip()

    if not texto:
        raise ValueError("El guion está vacío.")

    try:
        if not CREDENCIALES_PATH.exists():
            # En GitHub Actions no hay clave de Azure (repo público, no se sube):
            # ir directo a edge-tts sin ensuciar el log con una traza.
            raise FileNotFoundError("sin azure_speech_key.json")
        _generar_azure(texto, salida_path, voz)
        print(f"Audio generado (Azure Speech): {salida_path} (voz: {voz})")
    except Exception as e:
        # Fallback temporal (2026-09-21): la clave de Azure Speech sigue
        # devolviendo 401 muchas horas despues de crearla, no es solo el
        # retraso de activacion antifraude — ver aprendizajes.md. No bloquear
        # la produccion local por esto, edge-tts sigue funcionando bien en
        # local (aunque no en el sandbox cloud, ver aprendizajes.md 2026-09-20).
        print(f"AVISO: Azure Speech falló ({e}), usando edge-tts como respaldo.")
        await _generar_edge_tts(texto, salida_path, voz)
        print(f"Audio generado (edge-tts, respaldo): {salida_path} (voz: {voz})")


if __name__ == "__main__":
    import asyncio

    if len(sys.argv) < 3:
        print("Uso: python generar_audio.py <guion.txt> <salida.mp3> [voz]")
        sys.exit(1)

    guion = sys.argv[1]
    salida = sys.argv[2]
    voz = sys.argv[3] if len(sys.argv) > 3 else VOZ_POR_DEFECTO

    asyncio.run(generar(guion, salida, voz))
