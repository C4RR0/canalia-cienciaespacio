"""
Selección y atribución de la música de fondo del canal. Todas las pistas son
de Kevin MacLeod (incompetech.com), CC BY 4.0 -- ver musica/CREDITOS.txt.
La licencia exige atribución: cada vídeo que use una pista debe citarla en
la descripción (ver atribucion()).
"""
import random
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DIR_MUSICA = BASE / "musica"

# título real (para el crédito) -> nombre de archivo
PISTAS = {
    "Comfortable Mystery 3": "comfortable_mystery_3.mp3",
    "Comfortable Mystery 4": "comfortable_mystery_4.mp3",
    "Living Voyage": "living_voyage.mp3",
    "Ancient Rite": "ancient_rite.mp3",
    "Envision": "envision.mp3",
}


def elegir_pista(vid: str) -> tuple[Path, str]:
    """Elige una pista determinista (misma <id> -> misma pista siempre, para que
    regenerar un vídeo no le cambie la música) pero repartida entre las 5
    disponibles. Devuelve (ruta_mp3, titulo_para_credito)."""
    titulos = list(PISTAS.keys())
    idx = abs(hash(vid)) % len(titulos)
    titulo = titulos[idx]
    return DIR_MUSICA / PISTAS[titulo], titulo


def atribucion(titulo: str) -> str:
    return f'Música: "{titulo}" de Kevin MacLeod (incompetech.com) — Licencia: Creative Commons Attribution 4.0 (creativecommons.org/licenses/by/4.0/)'
