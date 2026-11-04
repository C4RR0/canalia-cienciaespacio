"""Informe de enganche: qué parte de las vistas son «comprometidas» (el espectador se queda en vez de deslizar).

Para el YPP cuentan las vistas válidas, no el contador público, y el algoritmo de Shorts reparte según
cuántos se quedan frente a cuántos deslizan. Por eso la métrica norte de cada Short es
vistas_comprometidas / vistas (objetivo ≥ 55 %; media del canal el 4/11/2026: 47 %).

Lee metricas/videos_enganche.csv (última fecha), videos.csv (títulos y fecha de publicación) y
temas_videos.csv (tema) y escribe metricas/enganche.md. Uso: python scripts/informe_enganche.py
"""
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "metricas"
MIN_VISTAS = 800  # por debajo, el porcentaje es ruido


def leer(nombre):
    ruta = DIR / nombre
    return list(csv.DictReader(open(ruta, encoding="utf-8"))) if ruta.exists() else []


def main():
    filas = leer("videos_enganche.csv")
    if not filas:
        print("sin datos")
        return
    ultima = max(f["fecha"] for f in filas)
    hoy = [f for f in filas if f["fecha"] == ultima and int(f["vistas"]) > 0]

    titulos, publicado = {}, {}
    for f in leer("videos.csv"):
        titulos[f["video_id"]] = f["titulo"]
        publicado[f["video_id"]] = f["publicado"][:10]
    temas = {f["video_id"]: f["tema"] for f in leer("temas_videos.csv")}

    def ratio(f):
        return int(f["vistas_comprometidas"]) / int(f["vistas"])

    total_v = sum(int(f["vistas"]) for f in hoy)
    total_c = sum(int(f["vistas_comprometidas"]) for f in hoy)

    por_tema = defaultdict(lambda: [0, 0, 0])
    for f in hoy:
        t = temas.get(f["video_id"], "sin tema")
        por_tema[t][0] += int(f["vistas"])
        por_tema[t][1] += int(f["vistas_comprometidas"])
        por_tema[t][2] += 1

    hace7 = (dt.date.fromisoformat(ultima) - dt.timedelta(days=7)).isoformat()
    recientes = [f for f in hoy if publicado.get(f["video_id"], "") >= hace7]
    rv = sum(int(f["vistas"]) for f in recientes)
    rc = sum(int(f["vistas_comprometidas"]) for f in recientes)

    fiables = sorted((f for f in hoy if int(f["vistas"]) >= MIN_VISTAS), key=ratio)

    def linea(f):
        return (f"| {100 * ratio(f):.0f} % | {f['vistas']} | {f['segundos_vistos_media']} s | "
                f"{temas.get(f['video_id'], '?')} | {titulos.get(f['video_id'], f['video_id'])[:80]} |")

    md = [f"# Enganche de los Shorts (datos del {ultima})", "",
          "Enganche = vistas comprometidas / vistas (quien se queda frente a quien desliza). Objetivo ≥ 55 %.", "",
          f"- Canal (últimos {len(hoy)} vídeos con datos): **{100 * total_c / max(total_v, 1):.0f} %** "
          f"({total_c:,} de {total_v:,}).".replace(",", "."),
          f"- Publicados en los últimos 7 días ({len(recientes)}): "
          f"**{100 * rc / max(rv, 1):.0f} %**." if recientes else "- Sin vídeos de los últimos 7 días con datos.",
          "", "## Por tema", "", "| Tema | Enganche | Vistas | Vídeos |", "|---|---|---|---|"]
    for t, (v, c, n) in sorted(por_tema.items(), key=lambda x: -x[1][1] / max(x[1][0], 1)):
        md.append(f"| {t} | {100 * c / max(v, 1):.0f} % | {v} | {n} |")
    cab = ["| Enganche | Vistas | Media vista | Tema | Título |", "|---|---|---|---|---|"]
    md += ["", f"## Los 10 que MÁS retienen (≥{MIN_VISTAS} vistas): copiar su tipo de tema y gancho", ""] + cab
    md += [linea(f) for f in reversed(fiables[-10:])]
    md += ["", f"## Los 10 que MENOS retienen (≥{MIN_VISTAS} vistas): evitar ese tipo de tema y gancho", ""] + cab
    md += [linea(f) for f in fiables[:10]]
    (DIR / "enganche.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"enganche.md escrito: canal {100 * total_c / max(total_v, 1):.0f} %")


if __name__ == "__main__":
    main()
