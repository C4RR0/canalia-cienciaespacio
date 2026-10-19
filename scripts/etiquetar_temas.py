"""Etiqueta cada vídeo con un tema por palabras clave del título.
Lee metricas/videos.csv (última fila de cada video_id) y escribe
metricas/temas_videos.csv (video_id,tema,duracion_s,vistas,titulo) y metricas/ranking_temas_v2.md.
No modifica videos.csv. Uso: python scripts/etiquetar_temas.py"""
import csv, re, unicodedata
from collections import defaultdict

REGLAS = [  # orden = prioridad
    ("parasitos", r"parasit|hongo controla|gusano obliga|gusano .*hormiga|quita a las ratas|obliga a (un|una|esta|este)|zombi|niñera|cebo"),
    ("lugares", r"lago|pueblo|isla|ciudad|agujero|cascada|desierto|sahara|chernobil|ardiendo|rio |lugar|niebla|volcan|groenlandia"),
    ("habilidades", r"sobrevive|regenera|dispara|corre sobre|inmortal|nunca duermen|viv(e|ir) mas de|puede vivir|se congela|respira|sin morir|vive "),
    ("animales", r"animal|pajaro|pez |pulpo|rana|lagarto|ave |ballena|tiburon|medusa|camaron|escarabajo|hormiga|avispa|murcielago|nutria|delfin|cuervo|elefante|koala|hipopotamo|tortuga|cucaracha|caracol|sapo|ratón|raton|marisco|oruga|abeja|primate|flamenco|jirafa|perro|gato|gusano"),
    ("historia", r"guerra|bomba|nuclear|cia |soldado|torre eiffel|hiroshima|roseta|piedra|espia|epidemia|baila|melaza|hombre"),
    ("espacio", r"universo|espacio|luna|jupiter|venus|saturno|nasa|astronauta|agujero negro|sol "),
    ("cuerpo_ciencia", r"cuerpo|bostezo|sangre|cielo es azul|rayo|metal|cerebro|miedo"),
]
def norm(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")

def tema(t):
    n = norm(t) + " "
    for nombre, rx in REGLAS:
        if re.search(rx, n): return nombre
    return "otros"

ult = {}
for r in csv.DictReader(open("metricas/videos.csv", encoding="utf8")):
    ult[r["video_id"]] = r
filas = [(v, tema(r["titulo"]), int(r["duracion_s"] or 0), int(r["vistas"] or 0), r["titulo"]) for v, r in ult.items()]
with open("metricas/temas_videos.csv", "w", newline="", encoding="utf8") as f:
    w = csv.writer(f); w.writerow(["video_id", "tema", "duracion_s", "vistas", "titulo"]); w.writerows(filas)
agg = defaultdict(list)
for _, t, d, v, _ in filas:
    if d >= 20 and d <= 40: agg[t].append(v)
    agg["_todos_" + t].append(v)
out = ["# Ranking de temas (Shorts de 20-40 s, vistas medias)\n", "| tema | vídeos | media vistas |", "|---|---|---|"]
for t in sorted([k for k in agg if not k.startswith("_")], key=lambda k: -sum(agg[k]) / len(agg[k])):
    out.append(f"| {t} | {len(agg[t])} | {sum(agg[t]) // len(agg[t])} |")
open("metricas/ranking_temas_v2.md", "w", encoding="utf8").write("\n".join(out) + "\n")
print("\n".join(out))
print("otros:", sum(1 for f in filas if f[1] == "otros"), "de", len(filas))
