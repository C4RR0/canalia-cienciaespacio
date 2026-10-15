"""
Orquestador maestro del pipeline: toma un config JSON y ejecuta TODO el proceso
de principio a fin (audio -> imagenes/diapositivas -> ensamblado -> subtitulos ->
miniatura -> subida a YouTube), reutilizando los scripts individuales ya probados
del proyecto. Pensado para producciones desatendidas y repetibles.

Uso:
    python producir_video.py config/<id>.json

Formato del config (JSON):
{
  "id": "short_010_pulpo_bomba",
  "formato": "curiosidad" | "lista" | "largo",
  "orientacion": "vertical" | "horizontal",
  "voz": "es-ES-AlvaroNeural",
  "tema_visual": "espacio|naturaleza|historia|familiar|adulto|curiosidades",

  // formato curiosidad/largo:
  "guion": "texto completo del guion narrado...",
  "queries_imagenes": ["query en ingles 1", "query en ingles 2", ...],
  "fuente_imagenes": "wikimedia" | "nasa",

  // formato lista (SIEMPRE horizontal, estilo XpressTV, con vídeo real de Pexels):
  "intro": "frase de apertura...",
  "hechos": ["dato 1", "dato 2", ...],
  "outro": "frase de cierre...",
  "queries_clips": ["query en ingles 1", ...]   // opcional, una por hecho; si se omite, se usan los propios "hechos" como query (peor resultado)

  "titulo": "...",
  "descripcion": "...",
  "tags": ["curiosidades", "datoscuriosos", ...],
  "categoria_id": "27",
  "privacidad": "public",
  "correcciones_subtitulos": {"texto_malo": "texto_bueno"}   // opcional
}

Escribe salidas/resultado_<id>.json con el resultado (video_id, url, rutas, duracion).
"""
import sys
import json
import time
import asyncio
import subprocess
from pathlib import Path
from pydub import AudioSegment

BASE = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))

import generar_audio
import suavizar_audio
import generar_imagenes
import buscar_imagenes_wikimedia as wiki
import buscar_imagenes_nasa as nasa
import buscar_videos_pexels as pexels
import generar_diapositiva_lista as diapositivas
import ensamblar_video_v2 as ensamblador
import ensamblar_lista_horizontal as ensamblador_lista
import generar_subtitulos
import corregir_subtitulos
import quemar_subtitulos
import generar_miniatura
import musica
import subir_youtube


def log(msg: str):
    print(f"\n=== {msg} ===", flush=True)


def anadir_silencio_final(audio_path: Path, ms: int = 800):
    """Añade un pequeño silencio al final del audio para que el vídeo no
    corte de golpe justo en la última palabra de la despedida — deja un
    respiro natural antes del corte final."""
    audio = AudioSegment.from_file(audio_path)
    (audio + AudioSegment.silent(duration=ms)).export(audio_path, format="mp3", bitrate="192k")


def resolucion(orientacion: str):
    return (1080, 1920) if orientacion == "vertical" else (1920, 1080)


def construir_texto_lista(cfg: dict) -> str:
    # No se dice "Número X" en voz alta: el número ya está grande en la diapositiva
    # y decirlo añadía ~1.3s por dato (con 25 datos, ~30s extra) sin aportar nada.
    partes = [cfg["intro"].strip()]
    for hecho in cfg["hechos"]:
        partes.append(hecho.strip())
    partes.append(cfg["outro"].strip())
    return "\n\n".join(partes)


def obtener_imagenes_reales(queries: list[str], carpeta_raw: Path, fuente: str) -> list[tuple[Path, bool]]:
    """Devuelve [(ruta, es_foto_real)]. es_foto_real=False cuando tuvo que caer al
    respaldo de IA (Pollinations), que suele dar planos abstractos poco reconocibles
    y por tanto no debe usarse como fotograma de miniatura."""
    carpeta_raw.mkdir(parents=True, exist_ok=True)
    rutas = []
    usadas = set()  # URLs de Wikimedia ya elegidas, para no repetir foto
    for i, query in enumerate(queries, start=1):
        salida = carpeta_raw / f"img_{i:02d}.jpg"
        if salida.exists():
            rutas.append((salida, True))
            continue
        obtenida = False
        es_real = True
        # 1) fuente preferida (wikimedia o nasa, imagenes reales)
        try:
            if fuente == "nasa":
                item = nasa.buscar_mejor_imagen(query)
                if item:
                    url = nasa.obtener_url_alta_resolucion(item)
                    if url:
                        nasa.descargar(url, salida)
                        obtenida = True
            else:
                url = wiki.buscar_archivo(query, excluir=usadas)
                if url:
                    wiki.descargar(url, salida)
                    obtenida = True
        except Exception as e:
            print(f"  [{i}] fuente principal falló para '{query}': {e}")

        # 2) fallback cruzado entre wikimedia/nasa
        if not obtenida:
            try:
                if fuente == "nasa":
                    url = wiki.buscar_archivo(query, excluir=usadas)
                    if url:
                        wiki.descargar(url, salida)
                        obtenida = True
                else:
                    item = nasa.buscar_mejor_imagen(query)
                    if item:
                        url = nasa.obtener_url_alta_resolucion(item)
                        if url:
                            nasa.descargar(url, salida)
                            obtenida = True
            except Exception as e:
                print(f"  [{i}] fuente alternativa falló para '{query}': {e}")

        # 3) fallback final: generación IA (Pollinations) para no dejar huecos
        if not obtenida:
            try:
                generar_imagenes.generar_imagen(query, 1024, 1024, salida, semilla=i * 1000 + 7)
                obtenida = True
                es_real = False
                print(f"  [{i}] usada imagen generada por IA como respaldo (no apta para miniatura)")
            except Exception as e:
                print(f"  [{i}] TODO falló para '{query}': {e}")

        if obtenida:
            rutas.append((salida, es_real))
        time.sleep(1)
    return rutas


def preparar_carpeta_final(rutas_origen: list[tuple[Path, bool]], carpeta_final: Path) -> list[bool]:
    carpeta_final.mkdir(parents=True, exist_ok=True)
    reales = []
    for i, (origen, es_real) in enumerate(rutas_origen, start=1):
        # Un hueco puede ser un clip de vídeo real (img_NN.mp4) en vez de una foto.
        destino = carpeta_final / f"img_{i:02d}{origen.suffix if origen.suffix == '.mp4' else '.jpg'}"
        if not destino.exists():
            destino.write_bytes(origen.read_bytes())
        reales.append(es_real)
    return reales


def mejor_segundo_miniatura(reales: list[bool] | None, dur_video: float) -> float:
    """Elige un instante del vídeo que corresponda a una imagen real (no IA abstracta)
    para extraer el fotograma de miniatura, priorizando una cercana al centro."""
    if not reales or not any(reales):
        return max(1.0, dur_video * 0.35)
    n = len(reales)
    centro = n / 2
    candidatos = [i for i, es_real in enumerate(reales) if es_real]
    mejor_i = min(candidatos, key=lambda i: abs((i + 0.5) - centro))
    return max(1.0, ((mejor_i + 0.5) / n) * dur_video)


def producir(cfg: dict) -> dict:
    vid = cfg["id"]
    formato = cfg["formato"]
    if formato == "lista":
        # El formato "lista" es horizontal de verdad (estilo XpressTV, ver
        # aprendizajes.md), no vertical: se fuerza sin importar el config.
        orientacion = "horizontal"
    else:
        orientacion = cfg.get("orientacion", "vertical" if formato != "largo" else "horizontal")
    ancho, alto = resolucion(orientacion)
    voz = cfg.get("voz", "es-ES-AlvaroNeural")
    tema_visual = cfg.get("tema_visual", "curiosidades")

    dir_guiones = BASE / "guiones"
    dir_audio = BASE / "audio"
    dir_imagenes = BASE / "imagenes"
    dir_subs = BASE / "subtitulos"
    dir_salidas = BASE / "salidas"
    dir_cola = BASE / "cola_audio"
    for d in (dir_guiones, dir_audio, dir_imagenes, dir_subs, dir_salidas):
        d.mkdir(exist_ok=True)

    # 1) Guion
    log("1/8 Guion")
    if formato == "lista":
        texto_guion = construir_texto_lista(cfg)
    else:
        texto_guion = cfg["guion"].strip()
    guion_path = dir_guiones / f"{vid}.txt"
    guion_path.write_text(texto_guion, encoding="utf-8")
    print(f"Guion escrito: {guion_path} ({len(texto_guion)} caracteres)")

    duraciones_clips = None  # solo se rellena en formato "lista"

    # Audio ya generado en local (ver generar_audio_pipeline.py): el TTS
    # (edge-tts) no puede salir a internet dentro del sandbox cloud porque
    # su cliente HTTP no respeta la CA del proxy de seguridad (ver
    # aprendizajes.md 2026-09-20). Si ya llega hecho en cola_audio/, se
    # reutiliza y se salta por completo el paso de TTS.
    audio_precocinado = dir_cola / f"{vid}_final.mp3"
    if audio_precocinado.exists():
        log("2/8 Audio (reutilizado de cola_audio/, generado en local)")
        audio_final = dir_audio / f"{vid}_final.mp3"
        audio_final.write_bytes(audio_precocinado.read_bytes())
        print(f"Audio reutilizado: {audio_precocinado} -> {audio_final}")
        if formato == "lista":
            meta_path = dir_cola / f"{vid}_duraciones.json"
            duraciones_clips = json.loads(meta_path.read_text(encoding="utf-8"))
    elif formato == "lista":
        # 2) Audio POR SEGMENTO (no todo junto de una vez): así se conoce la
        # duración exacta de cada dato narrado, y el clip de vídeo de ese dato
        # puede durar exactamente lo mismo en pantalla. Con un único bloque de
        # audio no hay forma de saber dónde empieza/termina cada frase sin
        # volver a transcribir, y repartir el vídeo a partes iguales
        # desincroniza el clip con lo que se está narrando (ver
        # aprendizajes.md, lista_001_25_gatos: un clip de "gato comiendo" se
        # veía mientras se narraba el dato de la nariz).
        log("2/8 Audio (TTS + suavizado, por segmento)")
        segmentos_texto = [cfg["intro"].strip()] + [h.strip() for h in cfg["hechos"]] + [cfg["outro"].strip()]
        dir_audio_seg = dir_audio / f"{vid}_segmentos"
        dir_audio_seg.mkdir(parents=True, exist_ok=True)
        rutas_segmentos = []
        for i, texto in enumerate(segmentos_texto):
            seg_txt = dir_audio_seg / f"seg_{i:02d}.txt"
            seg_bruto = dir_audio_seg / f"seg_{i:02d}_bruto.mp3"
            seg_final = dir_audio_seg / f"seg_{i:02d}.mp3"
            seg_txt.write_text(texto, encoding="utf-8")
            if not seg_final.exists():
                asyncio.run(generar_audio.generar(str(seg_txt), str(seg_bruto), voz))
                suavizar_audio.suavizar(str(seg_bruto), str(seg_final))
            rutas_segmentos.append(seg_final)

        ffmpeg_bin, ffprobe_bin = ensamblador_lista.resolver_bin()
        duraciones_segmentos = [ensamblador_lista.duracion_audio(ffprobe_bin, str(p)) for p in rutas_segmentos]

        audio_final = dir_audio / f"{vid}_final.mp3"
        lista_concat = dir_audio_seg / "lista_concat.txt"
        lista_concat.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in rutas_segmentos), encoding="utf-8"
        )
        subprocess.run([ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", str(lista_concat),
                         "-c", "copy", str(audio_final)], check=True, capture_output=True)
        print(f"Audio concatenado ({len(rutas_segmentos)} segmentos): {audio_final}")

        # el dato 1 se lleva también la duración del intro, y el último dato
        # se lleva también la del outro (no hay un clip de vídeo dedicado
        # para intro/outro, para no necesitar 2 búsquedas de vídeo extra).
        duraciones_clips = list(duraciones_segmentos[1:-1])
        duraciones_clips[0] += duraciones_segmentos[0]
        duraciones_clips[-1] += duraciones_segmentos[-1]

        # respiro final: que no corte de golpe justo tras la última palabra de
        # la despedida. Se añade también al último clip para que el vídeo se
        # quede ese instante extra en pantalla (si no, "-shortest" al mezclar
        # con el audio recortaría el silencio añadido y no serviría de nada).
        SILENCIO_FINAL_MS = 800
        anadir_silencio_final(audio_final, SILENCIO_FINAL_MS)
        duraciones_clips[-1] += SILENCIO_FINAL_MS / 1000
    else:
        # 2) Audio (bruto -> suavizado)
        log("2/8 Audio (TTS + suavizado)")
        audio_bruto = dir_audio / f"{vid}_bruto.mp3"
        audio_final = dir_audio / f"{vid}_final.mp3"
        asyncio.run(generar_audio.generar(str(guion_path), str(audio_bruto), voz))
        suavizar_audio.suavizar(str(audio_bruto), str(audio_final))
        # respiro final: que no corte de golpe justo tras la última palabra
        anadir_silencio_final(audio_final, 800)

    # 3) Imagenes / clips de vídeo
    log("3/8 Imágenes / clips de vídeo")
    carpeta_final_img = dir_imagenes / f"{vid}_final"
    reales = None
    if formato == "lista":
        carpeta_clips = dir_imagenes / f"{vid}_clips"
        carpeta_clips.mkdir(parents=True, exist_ok=True)
        queries_clips = cfg.get("queries_clips") or cfg["hechos"]
        query_generica = cfg.get("query_generica_clips")
        api_key = pexels.cargar_api_key()
        ultimo_clip_ok = None
        for i, query in enumerate(queries_clips, start=1):
            salida = carpeta_clips / f"clip_{i:02d}.mp4"
            if salida.exists():
                ultimo_clip_ok = salida
                continue
            obtenido = False
            for intento_query in [query] + ([query_generica] if query_generica else []):
                try:
                    video = pexels.buscar_mejor_clip(intento_query, api_key, "landscape")
                    if video:
                        url = pexels.obtener_url_archivo(video, "landscape")
                        if url:
                            pexels.descargar(url, salida)
                            print(f"  [{i}] '{intento_query}' -> {salida.name}")
                            obtenido = True
                            break
                except Exception as e:
                    print(f"  [{i}] error con '{intento_query}': {e}")
                time.sleep(1)
            if not obtenido:
                # ni la query específica ni la genérica dieron resultado: se
                # repite el último clip que sí funcionó, para garantizar 1
                # clip por dato (imprescindible para que las duraciones
                # cuadren exactamente con el guion, ver ensamblar_lista_horizontal.py)
                if ultimo_clip_ok is None:
                    raise RuntimeError(f"No se consiguió ningún clip de vídeo (ni de respaldo) para el dato {i}.")
                salida.write_bytes(ultimo_clip_ok.read_bytes())
                print(f"  [{i}] sin clip propio, reutilizado el del dato anterior")
            ultimo_clip_ok = salida
    else:
        carpeta_raw = dir_imagenes / vid
        # Imagenes ya conseguidas en local (ver generar_audio_pipeline.py):
        # Wikimedia/NASA/Pollinations tambien estan bloqueados por la
        # whitelist del sandbox cloud (igual que edge-tts, ver
        # aprendizajes.md 2026-09-21). Si ya llegan por cola_imagenes/, se
        # reutilizan y no se llama a ningun buscador de imagenes.
        cola_img = BASE / "cola_imagenes" / vid
        meta_cola = cola_img / "_reales.json"
        if meta_cola.exists():
            log("3/8 Imágenes (reutilizadas de cola_imagenes/, generadas en local)")
            carpeta_raw.mkdir(parents=True, exist_ok=True)
            reales_flags = json.loads(meta_cola.read_text(encoding="utf-8"))
            rutas = []
            for archivo, es_real in zip(sorted(p for p in cola_img.glob("img_*") if p.suffix in (".jpg", ".mp4")), reales_flags):
                destino = carpeta_raw / archivo.name
                destino.write_bytes(archivo.read_bytes())
                rutas.append((destino, es_real))
            print(f"{len(rutas)} imágenes reutilizadas de {cola_img}")
        else:
            fuente = cfg.get("fuente_imagenes", "wikimedia")
            rutas = obtener_imagenes_reales(cfg["queries_imagenes"], carpeta_raw, fuente)
        if not rutas:
            raise RuntimeError("No se consiguió ninguna imagen para el vídeo.")
        reales = preparar_carpeta_final(rutas, carpeta_final_img)

    # 4) Ensamblado
    log("4/8 Ensamblado de vídeo")
    ruta_musica, titulo_musica = musica.elegir_pista(vid)
    video_mudo_con_audio = dir_salidas / f"{vid}.mp4"
    if formato == "lista":
        ensamblador_lista.ensamblar(carpeta_clips, duraciones_clips, str(audio_final), str(video_mudo_con_audio), ancho, alto)
    else:
        # Shorts (curiosidad): cambio de plano cada ~2.5 s para retener; los
        # largos mantienen el ritmo pausado de documental.
        plano_max = cfg.get("plano_max", 2.5 if formato == "curiosidad" else None)
        ensamblador.ensamblar(carpeta_final_img, str(audio_final), str(video_mudo_con_audio), ancho, alto, None, None,
                              musica_path=ruta_musica, plano_max=plano_max)

    # 5) Subtitulos
    # Subtítulos ya transcritos y corregidos en local (ver
    # generar_audio_pipeline.py): faster-whisper necesita descargar su
    # modelo de Hugging Face Hub la primera vez, y ese dominio también
    # está bloqueado por la whitelist del sandbox cloud (ver
    # aprendizajes.md 2026-09-21 tarde). Si ya llegan por
    # cola_subtitulos/, se reutilizan y no se llama a whisper en absoluto.
    cola_srt = BASE / "cola_subtitulos" / f"{vid}_corregido.srt"
    cola_ass = BASE / "cola_subtitulos" / f"{vid}_corregido.ass"
    srt_corregido = dir_subs / f"{vid}_corregido.srt"
    ass_corregido = dir_subs / f"{vid}_corregido.ass"
    if cola_srt.exists():
        log("5/8 Subtítulos (reutilizados de cola_subtitulos/, transcritos en local)")
        srt_corregido.write_bytes(cola_srt.read_bytes())
        print(f"Subtítulos reutilizados: {cola_srt} -> {srt_corregido}")
        if cola_ass.exists():
            ass_corregido.write_bytes(cola_ass.read_bytes())
            print(f"Subtítulos palabra-por-palabra reutilizados: {cola_ass} -> {ass_corregido}")
    else:
        log("5/8 Subtítulos (transcripción + corrección + quemado)")
        srt_crudo = dir_subs / f"{vid}.srt"
        generar_subtitulos.generar_srt(str(audio_final), str(srt_crudo), "small")

        correcciones = cfg.get("correcciones_subtitulos")
        correcciones_path = None
        if correcciones:
            correcciones_path = dir_subs / f"correcciones_{vid}.txt"
            correcciones_path.write_text(
                "\n".join(f"{k}|{v}" for k, v in correcciones.items()), encoding="utf-8"
            )
        corregir_subtitulos.corregir(str(srt_crudo), str(srt_corregido), correcciones_path)

        palabras_json = srt_crudo.with_name(srt_crudo.stem + "_palabras.json")
        if palabras_json.exists():
            import generar_subtitulos_ass_palabras
            generar_subtitulos_ass_palabras.generar(palabras_json, ass_corregido, ancho, alto, correcciones_path)

    # Subtítulos palabra-por-palabra (más profesionales) si están disponibles,
    # si no, se cae al .srt de frase completa clásico.
    subs_para_quemar = ass_corregido if ass_corregido.exists() else srt_corregido
    if ass_corregido.exists() and cfg.get("formato") == "curiosidad" and not cfg.get("sin_marca"):
        import generar_subtitulos_ass_palabras
        generar_subtitulos_ass_palabras.anadir_gancho_y_marca(ass_corregido, cfg.get("hook_miniatura"))

    video_final = dir_salidas / f"{vid}_FINAL.mp4"
    quemar_subtitulos.quemar(str(video_mudo_con_audio), str(subs_para_quemar), str(video_final), "abajo", ancho, alto)

    # 6) Miniatura
    log("6/8 Miniatura")
    # segundo representativo: 35% del vídeo
    from subprocess import check_output
    ffprobe = generar_miniatura.shutil.which("ffprobe") or r"C:\Users\Sergio\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffprobe.exe"
    dur_video = float(json.loads(check_output([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video_final)]))["format"]["duration"])
    miniatura_path = dir_salidas / f"miniatura_{vid}.jpg"
    hook = cfg.get("hook_miniatura", cfg["titulo"][:60])
    cola_miniatura = BASE / "cola_miniaturas" / f"{vid}.jpg"
    if formato == "lista":
        # Miniatura dedicada (no extraída del vídeo): evita que el texto de una
        # diapositiva de fondo choque con el texto de la miniatura.
        diapositivas.generar_miniatura_lista(len(cfg["hechos"]), hook, str(miniatura_path), tema_visual)
    elif cola_miniatura.exists():
        # Miniatura IA cinematográfica ya generada en local (ver
        # generar_audio_pipeline.py): Pollinations está bloqueado en el
        # sandbox cloud igual que Wikimedia/whisper, así que se reutiliza
        # en vez de caer al método antiguo de fotograma+texto.
        miniatura_path.write_bytes(cola_miniatura.read_bytes())
        print(f"Miniatura IA reutilizada: {cola_miniatura} -> {miniatura_path}")
    else:
        segundo_frame = mejor_segundo_miniatura(reales, dur_video)
        # Se extrae del vídeo SIN subtítulos quemados (video_mudo_con_audio), no del
        # _FINAL: si no, el texto de los subtítulos queda fantasma detrás del gancho.
        generar_miniatura.generar(str(video_mudo_con_audio), segundo_frame, hook, str(miniatura_path), orientacion)

    # 7) Metadatos y subida
    log("7/8 Subida a YouTube")
    titulo_path = dir_salidas / f"titulo_{vid}.txt"
    descripcion_path = dir_salidas / f"descripcion_{vid}.txt"
    # Atribucion obligatoria (licencia CC BY 4.0) de la musica de fondo elegida
    # arriba, en el paso de ensamblado -- ver scripts/musica.py.
    descripcion_final = cfg["descripcion"].rstrip() + "\n\n" + musica.atribucion(titulo_musica)
    # Créditos de clips de vídeo de Commons (ver poner_clip.py): CC BY/BY-SA exige atribución.
    if cfg.get("creditos"):
        descripcion_final += "\n" + "\n".join(cfg["creditos"])
    titulo_path.write_text(cfg["titulo"], encoding="utf-8")
    descripcion_path.write_text(descripcion_final, encoding="utf-8")

    video_id = None
    error_subida = None
    if cfg.get("solo_render"):
        # Renderizado para otro canal (p. ej. CiberJuegos, que sube desde su
        # propia cola_listos/): se deja el vídeo en salidas/ sin subirlo.
        print("solo_render: vídeo renderizado, no se sube.")
    else:
        try:
            video_id = subir_youtube.subir(
                str(video_final), cfg["titulo"], descripcion_final, cfg.get("tags", []),
                cfg.get("categoria_id", "27"), cfg.get("privacidad", "public"), str(miniatura_path),
            )
        except Exception as e:
            error_subida = str(e)
            print(f"AVISO: la subida (o la miniatura) falló: {e}")

    # 8) Resultado
    log("8/8 Resultado")
    resultado = {
        "id": vid,
        "formato": formato,
        "titulo": cfg["titulo"],
        "video_id": video_id,
        "video_url": f"https://youtu.be/{video_id}" if video_id else None,
        "duracion_seg": round(dur_video, 1),
        "video_final": str(video_final),
        "miniatura": str(miniatura_path),
        "error_subida": error_subida,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    resultado_path = dir_salidas / f"resultado_{vid}.json"
    resultado_path.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return resultado


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python producir_video.py <config.json>")
        sys.exit(1)

    config_path = Path(sys.argv[1])
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    producir(cfg)
