"""
Vigilante diario (15/10/2026): con dos canales publicando solos, si algo se rompe
nadie se entera. Tras la foto de métricas, cuenta los Shorts publicados en las
últimas 24 h de cada canal; si alguno se queda corto, el workflow sale en rojo y
GitHub manda un correo.

Uso:
    python scripts/vigilar.py          (lee metricas/ y metricas_en/)
"""
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
MINIMO = {"metricas": ("Sabías Qué", 6), "metricas_en": ("Wild Facts Daily", 5)}


def publicados_24h(carpeta: Path) -> int | None:
    ruta = carpeta / "videos.csv"
    if not ruta.exists():
        return None
    filas = list(csv.DictReader(ruta.open(encoding="utf-8")))
    if not filas:
        return None
    ultima = max(f["fecha"] for f in filas)
    limite = datetime.now(timezone.utc) - timedelta(hours=24)
    return sum(1 for f in filas if f["fecha"] == ultima
               and datetime.fromisoformat(f["publicado"].replace("Z", "+00:00")) >= limite)


def main() -> int:
    mal = []
    for carpeta, (nombre, minimo) in MINIMO.items():
        n = publicados_24h(BASE / carpeta)
        if n is None:
            print(f"{nombre}: sin métricas todavía")
            continue
        print(f"{nombre}: {n} vídeos en las últimas 24 h (mínimo {minimo})")
        if n < minimo:
            mal.append(f"{nombre} solo publicó {n}")
    if mal:
        print("::error::" + "; ".join(mal) + " — revisar los runs de 'Publicar siguiente video'")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
