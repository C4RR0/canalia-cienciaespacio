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
import difflib
import json
import re
import sys
import unicodedata
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


def _normalizar(palabra: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", palabra.lower())
    return "".join(c for c in sin_tildes if c.isalnum())


def alinear_con_guion(palabras: list[dict], guion: str) -> list[dict]:
    """Sustituye el texto que oyó whisper por el del guion, conservando solo sus
    tiempos. Whisper destroza los nombres propios ("Halo" -> "A lo", "Steve Jobs"
    -> "Esteve Hobbes", "Snake" -> "Schnee") y a veces repite una frase entera
    sobre el silencio final; como el guion es exactamente lo que dice la voz,
    alinear las dos secuencias arregla todo eso sin listas de correcciones.
    - Tramos iguales o sustituidos: el texto del guion se reparte en el tiempo
      que ocupaban las palabras de whisper.
    - Palabras que whisper oyó y no están en el guion: se descartan.
    - Palabras del guion que whisper no oyó: se pegan a la palabra anterior."""
    tokens = guion.split()
    oidas = [w for w in palabras if _normalizar(w["word"])]
    if not tokens or not oidas:
        return palabras
    matcher = difflib.SequenceMatcher(
        None, [_normalizar(w["word"]) for w in oidas], [_normalizar(t) for t in tokens], autojunk=False
    )
    salida: list[dict] = []
    pendientes: list[str] = []  # palabras del guion sin palabra de whisper aún
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "delete":
            continue
        if op == "insert":
            if salida:
                salida[-1]["word"] += " " + " ".join(tokens[j1:j2])
            else:
                pendientes.extend(tokens[j1:j2])
            continue
        inicio, fin = oidas[i1]["start"], oidas[i2 - 1]["end"]
        trozo = tokens[j1:j2]
        paso = (fin - inicio) / len(trozo)
        for k, t in enumerate(trozo):
            if op == "equal" or len(trozo) == i2 - i1:
                w = oidas[i1 + k]
                salida.append({"start": w["start"], "end": w["end"], "word": t})
            else:
                salida.append({"start": inicio + k * paso, "end": inicio + (k + 1) * paso, "word": t})
        if pendientes:
            salida[-len(trozo)]["word"] = " ".join(pendientes) + " " + salida[-len(trozo)]["word"]
            pendientes = []
    return salida


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


def generar(palabras_json: Path, salida_ass: Path, ancho: int, alto: int, correcciones_path: Path | None = None,
            guion: str | None = None):
    palabras = json.loads(palabras_json.read_text(encoding="utf-8"))
    if guion:
        palabras = alinear_con_guion(palabras, guion)
    else:
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


GANCHO_S = 2.6  # cuánto dura el texto del gancho al empezar el vídeo
MARCA = "¿SABÍAS QUÉ?"


def _partir_en_dos(texto: str, max_chars: int = 13) -> str:
    """Parte el gancho en dos líneas por el espacio más centrado si es largo."""
    if len(texto) <= max_chars or " " not in texto:
        return texto
    mitad = len(texto) / 2
    corte = min((i for i, c in enumerate(texto) if c == " "), key=lambda i: abs(i - mitad))
    return texto[:corte] + r"\N" + texto[corte + 1:]


def anadir_gancho_y_marca(ass_path: Path, gancho: str | None, marca: str = MARCA):
    """15/10/2026, de lo aprendido sobre Shorts sin rostro: (1) gancho también en
    TEXTO en los primeros segundos (audio + imagen + texto a la vez), y (2) una
    seña visual fija del canal, reconocible con el sonido quitado. Se añade al
    .ass ya hecho, así vale también para los vídeos que ya estaban en cola."""
    contenido = ass_path.read_text(encoding="utf-8")
    if "Style: Gancho" in contenido:
        return
    ancho = int(re.search(r"PlayResX: (\d+)", contenido).group(1))
    alto = int(re.search(r"PlayResY: (\d+)", contenido).group(1))
    if alto <= ancho:
        return  # solo Shorts verticales
    # Texto negro sobre caja amarilla (BorderStyle 3: OutlineColour = color de la caja).
    estilos = (
        f"Style: Gancho,Arial Black,{ancho // 11},&H00000000,&H00000000,&H0000FFFF,&H0000FFFF,"
        f"-1,0,0,0,100,100,0,0,3,14,0,8,60,60,{int(alto * 0.15)},1\n"
        f"Style: Marca,Arial Black,{ancho // 19},&H1000FFFF,&H1000FFFF,&H60000000,&H00000000,"
        f"-1,0,0,0,100,100,2,0,1,3,0,8,40,40,{int(alto * 0.105)},1\n"
    )
    contenido = contenido.replace("\n[Events]", estilos + "\n[Events]", 1)
    lineas = [f"Dialogue: 1,{_tiempo_ass(GANCHO_S)},9:59:59.00,Marca,,0,0,0,,{marca}"]
    if gancho:
        texto = _partir_en_dos(gancho.strip().upper())
        lineas.append(f"Dialogue: 2,{_tiempo_ass(0)},{_tiempo_ass(GANCHO_S)},Gancho,,0,0,0,,"
                      f"{{\\fscx80\\fscy80\\t(0,150,\\fscx108\\fscy108)\\t(150,260,\\fscx100\\fscy100)"
                      f"\\fad(0,200)}}{texto}")
    ass_path.write_text(contenido.rstrip("\n") + "\n" + "\n".join(lineas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso: python generar_subtitulos_ass_palabras.py <palabras.json> <salida.ass> <ancho> <alto> [correcciones.txt]")
        sys.exit(1)

    correcciones = Path(sys.argv[5]) if len(sys.argv) > 5 else None
    generar(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), correcciones)
