"""
Genera subtítulos .ass "estilo viral": frases cortas de 2-4 palabras que van
cambiando en pantalla al ritmo del habla, con la palabra que se está
pronunciando en ese instante resaltada en color y con un pequeño efecto de
"pop" (rebote de escala). Es el estilo de captions dominante en shorts
profesionales (CapCut/Hormozi-style), mucho más dinámico que un subtítulo de
frase completa estática.

Usa el sidecar "<audio>_palabras.json" que genera generar_subtitulos.py
(word_timestamps de faster-whisper), NO el .srt de frase completa.

Uso:
    python generar_subtitulos_ass_palabras.py palabras.json salida.ass ancho alto [correcciones.txt]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from corregir_subtitulos import CORRECCIONES_GENERICAS

MAX_PALABRAS_POR_BLOQUE = 4
MAX_CHARS_POR_BLOQUE = 24
PAUSA_CORTE_S = 0.5  # una pausa >= esto entre palabras siempre corta el bloque
PAD_FINAL_S = 0.20  # cuanto se mantiene en pantalla la ultima palabra de un bloque
MIN_DUR_RESALTE_S = 0.32  # por debajo de esto el cambio de palabra resaltada
# "parpadea" y es ilegible (queja real: "van super rapido") -- palabras cortas
# (articulos, conjunciones) se agrupan con la siguiente hasta sumar este minimo,
# en vez de tener su propio paso de resaltado de 100-150ms.

COLOR_RESALTE = "&H0000FFFF&"  # amarillo (BGR), palabra que se esta diciendo ahora
COLOR_BASE = "&H00FFFFFF&"  # blanco, resto de palabras del bloque


def _correcciones_una_palabra(correcciones_path: Path | None):
    """Solo las correcciones de UNA palabra (sin espacios) tienen sentido aplicadas
    palabra a palabra; las de frase completa (p.ej. 'horizonte de, sucesos') se
    dejan para el .srt clasico, no se pueden remapear de forma fiable aqui."""
    todas = list(CORRECCIONES_GENERICAS)
    if correcciones_path and correcciones_path.exists():
        for linea in correcciones_path.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and "|" in linea:
                erroneo, correcto = linea.split("|", 1)
                todas.append((erroneo, correcto))
    return [(e, c) for e, c in todas if " " not in e.strip() and " " not in c.strip()]


def _aplicar_correcciones(palabra: str, correcciones) -> str:
    for erroneo, correcto in correcciones:
        if erroneo.lower() == palabra.lower().strip(".,;:!?¡¿"):
            sufijo = palabra[len(palabra.rstrip(".,;:!?¡¿")):]
            return correcto + sufijo
    return palabra


def _agrupar_en_bloques(palabras: list[dict]) -> list[list[dict]]:
    bloques = []
    actual = []
    for i, w in enumerate(palabras):
        candidato = actual + [w]
        texto_candidato = " ".join(p["word"] for p in candidato)
        excede = len(candidato) > MAX_PALABRAS_POR_BLOQUE or len(texto_candidato) > MAX_CHARS_POR_BLOQUE
        if actual and excede:
            bloques.append(actual)
            actual = [w]
        else:
            actual = candidato

        termina_frase = bool(re.search(r"[.!?…]$", w["word"]))
        hay_pausa_larga = i + 1 < len(palabras) and (palabras[i + 1]["start"] - w["end"]) >= PAUSA_CORTE_S
        if termina_frase or hay_pausa_larga:
            bloques.append(actual)
            actual = []
    if actual:
        bloques.append(actual)
    return bloques


def _tiempo_ass(segundos: float) -> str:
    cs = int(round(segundos * 100))
    h, resto = divmod(cs, 360000)
    m, resto = divmod(resto, 6000)
    s, cs = divmod(resto, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _renderizar_texto_bloque(bloque: list[dict], idx_inicio: int, idx_fin: int) -> str:
    """Resalta las palabras [idx_inicio, idx_fin] (ambas incluidas) del bloque —
    normalmente un rango de 1 palabra, más de una cuando se agruparon por ser
    demasiado cortas para tener su propio paso de resaltado (ver MIN_DUR_RESALTE_S)."""
    partes = []
    for i, w in enumerate(bloque):
        texto = w["word"].upper()
        if idx_inicio <= i <= idx_fin:
            partes.append(
                f"{{\\c{COLOR_RESALTE}\\t(0,90,\\fscx116\\fscy116)\\t(90,200,\\fscx100\\fscy100)}}{texto}{{\\r}}"
            )
        else:
            partes.append(texto)
    return " ".join(partes)


def generar(palabras_json: Path, salida_ass: Path, ancho: int, alto: int, correcciones_path: Path | None = None):
    palabras = json.loads(palabras_json.read_text(encoding="utf-8"))
    correcciones = _correcciones_una_palabra(correcciones_path)
    for w in palabras:
        w["word"] = _aplicar_correcciones(w["word"], correcciones)

    bloques = _agrupar_en_bloques(palabras)

    es_vertical = alto > ancho
    alineacion, margen_v = 2, int(alto * (0.22 if es_vertical else 0.10))
    margen_r = int(ancho * 0.10) if es_vertical else 40
    tamano_fuente = max(50, min(ancho, alto) // 15)

    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,{tamano_fuente},{COLOR_BASE},{COLOR_BASE},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,{alineacion},40,{margen_r},{margen_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lineas_dialogo = []
    for bi, bloque in enumerate(bloques):
        siguiente_bloque = bloques[bi + 1] if bi + 1 < len(bloques) else None
        fin_bloque = bloque[-1]["end"] + PAD_FINAL_S
        if siguiente_bloque:
            fin_bloque = min(fin_bloque, siguiente_bloque[0]["start"])
        wi = 0
        while wi < len(bloque):
            wj = wi
            inicio_grupo = bloque[wi]["start"]
            while True:
                fin_grupo = bloque[wj + 1]["start"] if wj + 1 < len(bloque) else fin_bloque
                if fin_grupo - inicio_grupo >= MIN_DUR_RESALTE_S or wj == len(bloque) - 1:
                    break
                wj += 1
            if fin_grupo <= inicio_grupo:
                wi = wj + 1
                continue
            texto = _renderizar_texto_bloque(bloque, wi, wj)
            lineas_dialogo.append(
                f"Dialogue: 0,{_tiempo_ass(inicio_grupo)},{_tiempo_ass(fin_grupo)},Default,,0,0,0,,{texto}"
            )
            wi = wj + 1

    salida_ass.write_text(cabecera + "\n".join(lineas_dialogo) + "\n", encoding="utf-8")
    print(f"Generados {len(bloques)} bloques / {len(lineas_dialogo)} diálogos en: {salida_ass}")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso: python generar_subtitulos_ass_palabras.py <palabras.json> <salida.ass> <ancho> <alto> [correcciones.txt]")
        sys.exit(1)

    correcciones = Path(sys.argv[5]) if len(sys.argv) > 5 else None
    generar(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), correcciones)
