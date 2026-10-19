# Ranking de temas de Sabías Qué por vistas (2026-10-19)

Fuente: última fila de cada vídeo en `metricas/videos.csv` (172 vídeos distintos, media 1.405 vistas).
Agrupación por palabras del título (aproximada; 122 vídeos caen en «otros»).

## Por duración
| Duración | Vídeos | Vistas medias |
|---|---|---|
| ≤35 s | 115 | 1.670 |
| 36-50 s | 19 | 1.310 |
| 51-65 s | 29 | 786 |
| >65 s | 9 | 207 |

Confirma la norma: los Shorts de 27-31 s rinden más; por encima de 50 s caen en picado.

## Por tema (media de vistas)
| Tema | Vídeos | Media |
|---|---|---|
| Animales | 18 | 1.762 |
| Parásitos | 9 | 1.523 |
| Lugares | 3 | 1.488 |
| Otros | 122 | 1.415 |
| Cuerpo humano | 7 | 978 |
| Espacio | 13 | 939 |

## Top 6 vídeos (todos de 27-30 s)
1. Pájaro que imita motosierras — 8.736
2. Dos animales que aterrorizan al tiburón blanco — 6.655
3. Avispa que convierte cucarachas en zombis — 6.482
4. Animal al que muerde una cobra y se la come — 6.459
5. Ciudad bajo tierra tras tirar una pared — 5.438
6. Pueblo ardiendo bajo tierra desde 1962 — 5.124

## Conclusiones
- Animales con un gancho extremo (depredador, zombi, imitación) y lugares imposibles lideran; espacio y cuerpo humano rinden por debajo de la media.
- `cola_prioridad.txt` ya prioriza parásitos y lugares imposibles; mantener 2 animales : 1 historia y dejar el espacio largo al final.
- Limitación: el agrupado por palabras es tosco; conviene etiquetar el tema en `videos.csv` para afinar.
