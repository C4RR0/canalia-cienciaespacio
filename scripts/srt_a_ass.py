"""
Convierte un .srt a .ass con control preciso de posición (evita ambigüedades de
resolución de guion que hacen que force_style falle al posicionar arriba/abajo).

Uso:
    python srt_a_ass.py entrada.srt salida.ass ancho alto [posicion]

posicion: "abajo" (defecto) o "arriba"
"""
import re
import sys
from pathlib import Path

PATRON_BLOQUE = re.compile(
    r"\d+\s*\n(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n(.*?)(?=\n\s*\n|\Z)",
    re.DOTALL,
)


def tiempo_ass(h, m, s, ms):
    cs = int(ms) // 10
    return f"{int(h)}:{int(m):02d}:{int(s):02d}.{cs:02d}"


def convertir(srt_path: str, ass_path: str, ancho: int, alto: int, posicion: str = "abajo"):
    texto = Path(srt_path).read_text(encoding="utf-8")

    es_vertical = alto > ancho  # formato Shorts: YouTube superpone su propia
    # interfaz (título, descripción, botones de like/comentarios/compartir) sobre
    # la parte inferior y el lateral derecho del vídeo. Un margen del 10% se queda
    # DEBAJO de esa interfaz y el texto se ve tapado.
    if posicion == "arriba":
        alineacion, margen_v = 8, int(alto * 0.06)
    else:
        alineacion, margen_v = 2, int(alto * (0.22 if es_vertical else 0.10))

    margen_r = int(ancho * 0.10) if es_vertical else 40  # deja libre la columna
    # de botones (me gusta/comentarios/compartir) del lateral derecho en Shorts

    tamano_fuente = max(28, min(ancho, alto) // 27)

    cabecera = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {ancho}
PlayResY: {alto}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{tamano_fuente},&H00FFFFFF,&H00FFFFFF,&H00000000,&H40000000,-1,0,0,0,100,100,0,0,3,4,0,{alineacion},40,{margen_r},{margen_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lineas_dialogo = []
    for m in PATRON_BLOQUE.finditer(texto):
        h1, m1, s1, ms1, h2, m2, s2, ms2, cuerpo = m.groups()
        inicio = tiempo_ass(h1, m1, s1, ms1)
        fin = tiempo_ass(h2, m2, s2, ms2)
        cuerpo_limpio = " ".join(l.strip() for l in cuerpo.strip().splitlines())
        cuerpo_limpio = cuerpo_limpio.replace("{", "(").replace("}", ")")
        lineas_dialogo.append(f"Dialogue: 0,{inicio},{fin},Default,,0,0,0,,{cuerpo_limpio}")

    Path(ass_path).write_text(cabecera + "\n".join(lineas_dialogo) + "\n", encoding="utf-8")
    print(f"Generados {len(lineas_dialogo)} diálogos en: {ass_path}")


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso: python srt_a_ass.py <entrada.srt> <salida.ass> <ancho> <alto> [posicion: abajo|arriba]")
        sys.exit(1)

    posicion = sys.argv[5] if len(sys.argv) > 5 else "abajo"
    convertir(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), posicion)
