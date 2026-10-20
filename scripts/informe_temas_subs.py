"""Qué temas convierten vistas en suscriptores (para llegar antes a los 500 del YPP).
Cruza metricas/temas_videos.csv (tema de cada vídeo, de etiquetar_temas.py) con
metricas/videos_analytics.csv (vistas y subs ganados acumulados por vídeo, foto diaria)
y escribe metricas/temas_subs.md: total acumulado y últimos 7 días por tema.
Uso: python scripts/etiquetar_temas.py && python scripts/informe_temas_subs.py"""
import csv
from collections import defaultdict
from datetime import date, timedelta

temas = {r["video_id"]: r["tema"] for r in csv.DictReader(open("metricas/temas_videos.csv", encoding="utf8"))}
fotos = defaultdict(dict)  # fecha -> video_id -> (vistas, subs)
for r in csv.DictReader(open("metricas/videos_analytics.csv", encoding="utf8")):
    fotos[r["fecha"]][r["video_id"]] = (int(r["vistas"] or 0), int(r["subs_ganados"] or 0))
hoy = max(fotos)
objetivo = (date.fromisoformat(hoy) - timedelta(days=7)).isoformat()
antes = max((f for f in fotos if f <= objetivo), default=None)  # la foto más cercana a hace 7 días


def por_tema(actual, previa):
    agg = defaultdict(lambda: [0, 0, 0])  # vídeos, vistas, subs
    for v, (vistas, subs) in actual.items():
        pv, ps = previa.get(v, (0, 0))
        a = agg[temas.get(v, "sin_etiquetar")]
        a[0] += 1
        a[1] += vistas - pv
        a[2] += subs - ps
    return agg


def tabla(agg):
    filas = ["| tema | vídeos | vistas | subs | subs por 1.000 vistas |", "|---|---|---|---|---|"]
    for t, (n, vistas, subs) in sorted(agg.items(), key=lambda kv: -(kv[1][2] / kv[1][1] if kv[1][1] else 0)):
        filas.append(f"| {t} | {n} | {vistas:,} | {subs} | {1000 * subs / vistas:.2f} |".replace(",", ".") if vistas
                     else f"| {t} | {n} | 0 | {subs} | - |")
    n, vistas, subs = (sum(a[i] for a in agg.values()) for i in range(3))
    filas.append(f"| **total** | {n} | {vistas:,} | {subs} | {1000 * subs / vistas:.2f} |".replace(",", ".") if vistas
                 else f"| **total** | {n} | 0 | {subs} | - |")
    return filas


out = [f"# Suscriptores ganados por tema (foto del {hoy})", "",
       "Ordenado por suscriptores por cada 1.000 vistas: arriba los temas que mejor convierten.", ""]
if antes:
    out += [f"## Últimos 7 días ({antes} → {hoy})", ""] + tabla(por_tema(fotos[hoy], fotos[antes])) + [""]
out += ["## Acumulado desde el 1/9", ""] + tabla(por_tema(fotos[hoy], {}))
open("metricas/temas_subs.md", "w", encoding="utf8").write("\n".join(out) + "\n")
print("\n".join(out))
