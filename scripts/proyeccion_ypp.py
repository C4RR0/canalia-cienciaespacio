"""Proyección al YPP de Sabías Qué a partir de metricas/canal.csv -> metricas/proyeccion_ypp.md.
Requisitos usados: 500 suscriptores y 3.000.000 de visualizaciones de Shorts en 90 días (33.333/día)."""
import csv, datetime as dt
OBJ_SUBS, OBJ_VISTAS_90 = 500, 3_000_000
filas = list(csv.DictReader(open("metricas/canal.csv", encoding="utf-8")))
d = [(dt.date.fromisoformat(f["fecha"]), int(f["suscriptores"]), int(f["vistas"])) for f in filas]
hoy, subs, vistas = d[-1]
def media(n):
    ini = d[max(0, len(d) - 1 - n)]
    dias = (hoy - ini[0]).days or 1
    return (subs - ini[1]) / dias, (vistas - ini[2]) / dias, dias
s7, v7, n7 = media(7)
faltan = OBJ_SUBS - subs
ref90 = d[max(0, len(d) - 1 - 90)]
v90 = vistas - ref90[2]
dias90 = (hoy - ref90[0]).days
def fecha(dias): return (hoy + dt.timedelta(days=round(dias))).strftime("%d/%m/%Y")
L = [f"# Proyección al YPP (datos de {hoy:%d/%m/%Y})", ""]
L += [f"- Suscriptores: {subs}/{OBJ_SUBS}, faltan {max(faltan,0)}.",
      f"- Ritmo últimos {n7} días: {s7:.1f} subs/día y {v7:,.0f} vistas/día.".replace(",", ".")]
if faltan > 0 and s7 > 0:
    L.append(f"- Al ritmo actual los {OBJ_SUBS} subs llegan en {faltan/s7:.0f} días (≈ {fecha(faltan/s7)}); para llegar en 30 días hacen falta {faltan/30:.1f} subs/día.")
L += [f"- Vistas de los últimos {dias90} días (los datos empiezan el {ref90[0]:%d/%m}): {v90:,}.".replace(",", "."),
      f"- Objetivo: {OBJ_VISTAS_90:,} en 90 días = {OBJ_VISTAS_90/90:,.0f}/día. Ritmo actual = {v7/(OBJ_VISTAS_90/90)*100:.0f} % del necesario.".replace(",", ".")]
if v7 > 0:
    L.append(f"- Con {v7:,.0f} vistas/día, en 90 días se acumularían {v7*90:,.0f} vistas ({v7*90/OBJ_VISTAS_90*100:.0f} % del objetivo).".replace(",", "."))
L += ["", "Nota: las vistas del canal incluyen largos; es una aproximación. Alternativa de YouTube: 3.000 h de reproducción en 12 meses."]
open("metricas/proyeccion_ypp.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
