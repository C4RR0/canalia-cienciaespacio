"""
Recopilación horizontal (vídeo largo, 1920x1080) montada con Shorts YA
publicados: cuenta atrás "#20 ... #1" con tarjeta narrada entre cada uno.

Por qué: los Shorts no suman horas de visualización para el YPP (hacen falta
4.000 h de vídeo largo) y el canal no tiene largos que funcionen. Esto
reutiliza el material ya revisado (fotos con QA, audio, subtítulos), así que
no cuesta producción nueva.

El material de cada Short se recupera del historial de git: el commit de
limpieza de GitHub Actions borra cola_imagenes/<id>, cola_audio/<id>_final.mp3
y cola_subtitulos/<id>_corregido.ass, así que su commit padre los tiene tal
cual se publicaron (con las fotos ya corregidas en la QA).

Uso:
    python producir_recopilacion.py produccion_config/recop_XXX.json [--subir]
Sin --subir solo renderiza (salidas/<id>/<id>_FINAL.mp4 + miniatura +
descripción con capítulos) para revisarlo antes.
"""
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import ensamblar_video_v2 as ensamblador
import generar_audio
import generar_miniatura
import musica
import quemar_subtitulos
import suavizar_audio

BASE = Path(__file__).resolve().parent.parent
ANCHO, ALTO = 1920, 1080
PLANO_MAX = 3.0  # algo más pausado que en los Shorts (2,5 s), sigue siendo dinámico
FFMPEG, FFPROBE = ensamblador.resolver_bin()
# Parámetros comunes de todas las piezas, para poder unirlas con -c copy.
CODIF = ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", "30", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise RuntimeError(f"Falló: {' '.join(map(str, cmd[:6]))}...")


def duracion(ruta: Path) -> float:
    return ensamblador.duracion_audio(FFPROBE, str(ruta))


def recuperar_short(vid: str, destino: Path):
    """Saca de git las fotos, el audio y el .ass con los que se publicó el Short."""
    if (destino / "audio.mp3").exists():
        return
    commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", f"cola_imagenes/{vid}"], cwd=BASE, text=True).strip()
    if not commit:
        raise RuntimeError(f"{vid}: no está en el historial de cola_imagenes/")
    padre = f"{commit}^"
    rutas = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", padre, "--",
         f"cola_imagenes/{vid}", f"cola_audio/{vid}_final.mp3", f"cola_subtitulos/{vid}_corregido.ass"],
        cwd=BASE, text=True).split()
    (destino / "img").mkdir(parents=True, exist_ok=True)
    for ruta in rutas:
        datos = subprocess.check_output(["git", "show", f"{padre}:{ruta}"], cwd=BASE)
        if ruta.endswith(".mp3"):
            (destino / "audio.mp3").write_bytes(datos)
        elif ruta.endswith(".ass"):
            (destino / "vertical.ass").write_bytes(datos)
        elif ruta.endswith(".jpg"):
            (destino / "img" / Path(ruta).name).write_bytes(datos)
    if not (destino / "audio.mp3").exists() or not (destino / "vertical.ass").exists():
        raise RuntimeError(f"{vid}: falta audio o subtítulos en {padre}")


def ass_a_horizontal(origen: Path, salida: Path):
    """Mismo texto y tiempos; solo cambia el lienzo y los márgenes (mismos
    valores que generar_subtitulos_ass_palabras usa para horizontal)."""
    txt = origen.read_text(encoding="utf-8")
    txt = re.sub(r"PlayResX: \d+", f"PlayResX: {ANCHO}", txt)
    txt = re.sub(r"PlayResY: \d+", f"PlayResY: {ALTO}", txt)
    # Últimos campos del estilo: Alignment, MarginL, MarginR, MarginV, Encoding.
    txt, n = re.subn(r"^(Style: Default,[^\n]*?,\d+),\d+,\d+,\d+,(\d+)(\r?)$",
                     lambda m: f"{m.group(1)},40,40,{int(ALTO * 0.10)},{m.group(2)}{m.group(3)}", txt, flags=re.M)
    if n != 1:
        raise RuntimeError(f"{origen}: no se reconoce la línea Style")
    salida.write_text(txt, encoding="utf-8")


def normalizar(entrada: Path, salida: Path):
    run([FFMPEG, "-y", "-i", str(entrada), *CODIF, str(salida)])


def tts(texto: str, voz: str, salida: Path):
    if salida.exists():
        return
    txt = salida.with_suffix(".txt")
    txt.write_text(texto, encoding="utf-8")
    bruto = salida.with_name(salida.stem + "_bruto.mp3")
    asyncio.run(generar_audio.generar(str(txt), str(bruto), voz))
    suavizar_audio.suavizar(str(bruto), str(salida))


def render_pieza(carpeta_img: Path, audio: Path, ass: Path, clave: str, trabajo: Path) -> tuple[Path, str]:
    """Fotos + voz + música + subtítulos quemados -> pieza normalizada."""
    pista, titulo_musica = musica.elegir_pista(clave)
    mudo = trabajo / "mudo.mp4"
    ensamblador.ensamblar(carpeta_img, str(audio), str(mudo), ANCHO, ALTO, None, None,
                          musica_path=pista, plano_max=PLANO_MAX)
    con_subs = trabajo / "subs.mp4"
    quemar_subtitulos.quemar(str(mudo), str(ass), str(con_subs), "abajo", ANCHO, ALTO)
    pieza = trabajo / "pieza.mp4"
    normalizar(con_subs, pieza)
    return pieza, titulo_musica


def tarjeta(numero: int, nombre: str, fondo: Path, audio: Path, salida: Path):
    """Tarjeta de cuenta atrás: foto del animal desenfocada + '#N' + nombre,
    con la voz diciendo 'Número N. <nombre>.'"""
    img = Image.open(fondo).convert("RGB")
    escala = max(ANCHO / img.width, ALTO / img.height)
    img = img.resize((int(img.width * escala) + 1, int(img.height * escala) + 1))
    x0, y0 = (img.width - ANCHO) // 2, (img.height - ALTO) // 2
    img = img.crop((x0, y0, x0 + ANCHO, y0 + ALTO)).filter(ImageFilter.GaussianBlur(18))
    img = ImageEnhance.Brightness(img).enhance(0.45)
    d = ImageDraw.Draw(img)
    f_num, f_nom = generar_miniatura.cargar_fuente(330), generar_miniatura.cargar_fuente(110)
    for texto, fuente, color, y in ((f"#{numero}", f_num, (255, 214, 0), ALTO * 0.40),
                                    (nombre.upper(), f_nom, (255, 255, 255), ALTO * 0.72)):
        d.text((ANCHO / 2, y), texto, font=fuente, fill=color, anchor="mm",
               stroke_width=10, stroke_fill=(0, 0, 0))
    png = salida.with_suffix(".png")
    img.save(png)
    dur = duracion(audio) + 0.6
    n_frames = int(dur * 30)
    run([FFMPEG, "-y", "-loop", "1", "-t", f"{dur:.3f}", "-i", str(png), "-i", str(audio),
         "-filter_complex",
         f"[0:v]scale=4000:-1,zoompan=z='1+0.06*on/{n_frames}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2'"
         f":d={n_frames}:s={ANCHO}x{ALTO}:fps=30,format=yuv420p[v];[1:a]apad[a]",
         "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}", *CODIF, str(salida)])


def pieza_narrada(texto: str, imagenes: list[Path], voz: str, trabajo: Path) -> tuple[Path, str]:
    """Intro / cierre: voz nueva sobre fotos de varios Shorts, con subtítulos."""
    import generar_subtitulos
    import generar_subtitulos_ass_palabras
    trabajo.mkdir(parents=True, exist_ok=True)
    carpeta = trabajo / "img"
    carpeta.mkdir(exist_ok=True)
    for i, img in enumerate(imagenes, 1):
        (carpeta / f"img_{i:02d}.jpg").write_bytes(img.read_bytes())
    audio = trabajo / "voz.mp3"
    tts(texto, voz, audio)
    srt = trabajo / "voz.srt"
    generar_subtitulos.generar_srt(str(audio), str(srt), "small")
    ass = trabajo / "voz.ass"
    generar_subtitulos_ass_palabras.generar(srt.with_name("voz_palabras.json"), ass, ANCHO, ALTO, None, guion=texto)
    return render_pieza(carpeta, audio, ass, trabajo.name, trabajo)


def mmss(seg: float) -> str:
    seg = int(seg)
    return f"{seg // 60}:{seg % 60:02d}"


def producir(cfg: dict, subir: bool):
    rid, voz = cfg["id"], cfg["voz"]
    dir_out = BASE / "salidas" / rid
    dir_out.mkdir(parents=True, exist_ok=True)
    items = cfg["items"]
    total = len(items)

    for it in items:
        recuperar_short(it["id"], dir_out / it["id"])
    print(f"Material de {total} Shorts recuperado de git")

    piezas, capitulos, pistas = [], [], set()

    def imgs(vid, n):
        return sorted((dir_out / vid / "img").glob("img_*.jpg"))[:n]

    def elegidas(lista):
        # Fotos elegidas a mano ([id, n]): la primera es lo primero que se ve
        # del vídeo, y en cola hay esquemas científicos que no sirven de apertura.
        return [imgs(v, n)[n - 1] for v, n in lista]

    intro, pista = pieza_narrada(cfg["intro"], elegidas(cfg["intro_imagenes"]), voz, dir_out / "_intro")
    piezas.append(intro)
    pistas.add(pista)
    capitulos.append("Intro")

    for pos, it in enumerate(items):
        numero = total - pos
        vid = it["id"]
        trabajo = dir_out / vid
        voz_tarjeta = trabajo / "tarjeta.mp3"
        tts(f"Número {numero}. {it['nombre']}.", voz, voz_tarjeta)
        fondo = imgs(vid, 1)[0]
        pieza_tarjeta = trabajo / "tarjeta.mp4"
        tarjeta(numero, it["nombre"], fondo, voz_tarjeta, pieza_tarjeta)
        piezas.append(pieza_tarjeta)
        capitulos.append(f"#{numero} {it['nombre']}")

        if (trabajo / "pieza.mp4").exists():
            piezas.append(trabajo / "pieza.mp4")
            pistas.add(musica.elegir_pista(vid)[1])
            continue
        ass = trabajo / "horizontal.ass"
        ass_a_horizontal(trabajo / "vertical.ass", ass)
        pieza, pista = render_pieza(trabajo / "img", trabajo / "audio.mp3", ass, vid, trabajo)
        piezas.append(pieza)
        pistas.add(pista)
        print(f"#{numero} {vid} OK")

    cierre, pista = pieza_narrada(cfg["outro"], elegidas(cfg["outro_imagenes"]), voz, dir_out / "_cierre")
    piezas.append(cierre)
    pistas.add(pista)

    lista = dir_out / "concat.txt"
    lista.write_text("".join(f"file '{p.as_posix()}'\n" for p in piezas), encoding="utf-8")
    final = dir_out / f"{rid}_FINAL.mp4"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy",
         "-movflags", "+faststart", str(final)])

    # Capítulos: cada uno empieza en la intro o en la tarjeta de su número.
    t, marcas = 0.0, []
    piezas_con_capitulo = [piezas[0]] + piezas[1:-1:2]
    for p in piezas:
        if p in piezas_con_capitulo:
            marcas.append(t)
        t += duracion(p)
    lineas_cap = "\n".join(f"{mmss(m)} {c}" for m, c in zip(marcas, capitulos))
    creditos = "\n".join(musica.atribucion(p) for p in sorted(pistas))
    descripcion = f"{cfg['descripcion'].rstrip()}\n\n{lineas_cap}\n\n{creditos}"
    (dir_out / "descripcion.txt").write_text(descripcion, encoding="utf-8")

    vid_mini, n_mini = cfg["miniatura_imagen"]
    base_mini = sorted((dir_out / vid_mini / "img").glob("img_*.jpg"))[n_mini - 1]
    miniatura = dir_out / "miniatura.jpg"
    generar_miniatura.componer(Image.open(base_mini), cfg["hook_miniatura"], "horizontal").save(miniatura, quality=92)

    print(f"FINAL: {final} ({mmss(t)})")
    print(descripcion)

    if subir:
        import subir_youtube
        video_id = subir_youtube.subir(str(final), cfg["titulo"], descripcion, cfg["tags"],
                                       cfg["categoria_id"], cfg["privacidad"], str(miniatura))
        print(f"PUBLICADO=https://youtu.be/{video_id}")


if __name__ == "__main__":
    ruta_cfg = Path(sys.argv[1])
    producir(json.loads(ruta_cfg.read_text(encoding="utf-8")), "--subir" in sys.argv)
