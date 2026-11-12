#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
 Analizador de Archivos - PRO
===============================================================================
Herramienta de escritorio (Tkinter, solo librería estándar de Python) para
buscar, filtrar, y detectar archivos duplicados en una o varias carpetas,
combinando múltiples criterios de búsqueda a la vez.

FILTROS DISPONIBLES (se pueden activar varios a la vez):
  - Nombre exacto (literal), con opción de ignorar la extensión.
  - Nombre que contiene una palabra/texto.
  - Extensión / tipo de archivo (una o varias).
  - Contenido que contiene una palabra o texto.
  - Contenido que contiene un número (con opción de "número exacto", es
    decir, que no forme parte de un número más largo).
  - Tamaño exacto (en bytes).
  - Tamaño dentro de un rango (mínimo / máximo, en bytes).
  - Fecha de modificación (después de / antes de una fecha dada).
  - Duplicados EXACTOS: mismo contenido byte a byte (comparación por hash
    SHA-256).
  - Duplicados por TAMAÑO: mismo peso en bytes, aunque el contenido difiera.

Los filtros activos se pueden combinar en modo "Y" (deben cumplirse TODOS)
o en modo "O" (basta con que se cumpla UNO). El escaneo completo corre en
un hilo de segundo plano para que la ventana nunca se quede congelada,
incluso analizando carpetas con miles de archivos; se muestra una barra de
progreso y hay un botón para cancelar en cualquier momento.

INFORMACIÓN MOSTRADA POR ARCHIVO EN LOS RESULTADOS:
  - Nombre, ruta completa, tamaño ("espacio" que ocupa en disco) y fecha
    de modificación.
  - Motivo(s) por los que ese archivo aparece en la lista (qué filtro(s)
    ha cumplido, o a qué grupo de duplicados pertenece).
  - Número de ERRORES detectados al analizar ese archivo en concreto (por
    ejemplo: permisos denegados al leer su contenido, o al calcular su
    hash). Esto permite detectar rápidamente archivos "problemáticos"
    (protegidos, corruptos, bloqueados por otro programa, etc.) sin que
    esos errores interrumpan el análisis del resto de archivos.

RESUMEN DE ESPACIO EN DISCO:
  Tras cada análisis se muestra un resumen con:
  - Espacio total ocupado por los archivos encontrados.
  - Espacio "recuperable" si se eliminan los duplicados repetidos
    (conservando 1 copia de cada grupo).
  - Espacio libre actualmente en el/los disco(s) de las carpetas analizadas.
  - Número de archivos con algún error y número de carpetas a las que no
    se ha podido acceder (por permisos, por ejemplo).

ACCIONES SOBRE LOS RESULTADOS:
  - Exportar a CSV, abrir la ubicación del archivo, copiar su ruta.
  - Seleccionar todo o solo los duplicados con un clic.
  - Eliminar los archivos seleccionados.
  - Mover los archivos seleccionados a una carpeta elegida por el usuario;
    si ya existe un archivo con el mismo nombre en destino, se renombra
    automáticamente (nunca se sobrescribe ni se pierde nada).
  - Para grupos de duplicados: eliminar el resto (conservando 1 copia) o
    moverlos a una carpeta, con el mismo renombrado automático anti-colisión.
  - Ver el detalle de los errores registrados en un archivo concreto.
===============================================================================
"""

# ------------------------------------------------------------------------
# IMPORTS
# ------------------------------------------------------------------------
# Todo el programa usa EXCLUSIVAMENTE la librería estándar de Python, para
# que se pueda ejecutar en cualquier PC con Python instalado sin necesidad
# de instalar paquetes adicionales (pip install ...), y para que el .exe
# generado con PyInstaller no dependa de nada externo (ver build_exe.bat).
# ------------------------------------------------------------------------
import os               # Recorrer carpetas, leer metadatos de archivos, borrar, etc.
import re                # Expresiones regulares (búsqueda de números "exactos" en texto)
import csv               # Exportar los resultados a un archivo .csv
import sys                # Uso menor (comprobaciones de entorno)
import shutil              # Mover archivos (shutil.move) y consultar espacio en disco (shutil.disk_usage)
import hashlib               # Calcular el hash SHA-256 de los archivos (detección de duplicados exactos)
import threading                # Ejecutar el escaneo en segundo plano sin congelar la interfaz
import subprocess                 # Abrir el explorador de archivos del sistema operativo
import platform                    # Detectar si estamos en Windows / macOS / Linux
from csv_safety import csv_safe_cell
from datetime import datetime         # Fechas de modificación y filtros por fecha

import tkinter as tk                     # Interfaz gráfica
from tkinter import ttk, filedialog, messagebox   # Widgets modernos, diálogos de archivo y de aviso

APP_TITLE = "Analizador de Archivos PRO"

# Límite de tamaño (bytes) para intentar leer el contenido de un archivo como
# texto. Los archivos más grandes que esto NO se abren para las búsquedas de
# "contenido contiene texto/número" (evita bloquear el programa intentando
# leer, por ejemplo, un vídeo de 4 GB como si fuera un archivo de texto).
# El usuario puede cambiar este límite desde la propia interfaz.
DEFAULT_MAX_TEXT_READ = 50 * 1024 * 1024  # 50 MB

# Tamaño de bloque usado al calcular el hash de un archivo. Leer por bloques
# (en vez de cargar el archivo entero en memoria) permite calcular el hash
# incluso de archivos muy grandes sin agotar la RAM del equipo.
HASH_CHUNK_SIZE = 1024 * 1024  # 1 MB por bloque


# ==========================================================================
# FUNCIONES DE UTILIDAD (no dependen de la interfaz gráfica)
# ==========================================================================

def human_size(num_bytes) -> str:
    """Convierte un número de bytes en una cadena legible por humanos.

    Ejemplos: 512 -> '512 B', 2048 -> '2.0 KB', 5_368_709_120 -> '5.0 GB'.
    Se usa tanto en la tabla de resultados como en el resumen de espacio.
    """
    num_bytes = float(num_bytes)
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < step:
            # Para bytes mostramos un entero (no tiene sentido "512.0 B")
            return f"{int(num_bytes)} B" if unit == "B" else f"{num_bytes:3.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"  # por si algún día alguien analiza un disco absurdamente grande


def get_disk_free_space(path: str):
    """Devuelve (bytes_libres, texto_legible) del disco donde está 'path'.

    Se usa para mostrar en el resumen cuánto espacio libre queda disponible
    en el disco de cada carpeta analizada. Si por lo que sea no se puede
    consultar (ruta de red caída, permisos, etc.), devuelve (None, None) en
    vez de interrumpir el programa.
    """
    try:
        uso = shutil.disk_usage(path)
        return uso.free, human_size(uso.free)
    except (OSError, PermissionError, ValueError):
        return None, None


def file_hash(path: str, chunk_size: int = HASH_CHUNK_SIZE):
    """Calcula el hash SHA-256 de un archivo leyéndolo por bloques.

    Devuelve una tupla (hash_hexadecimal_o_None, mensaje_de_error_o_None).
    Nunca lanza una excepción hacia fuera: cualquier problema de E/S o de
    permisos se convierte en un mensaje de error legible que el llamador
    puede mostrar en la columna "Errores" de ese archivo, sin abortar el
    análisis del resto de archivos.
    """
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest(), None
    except (OSError, PermissionError) as e:
        return None, f"No se pudo calcular el hash (posible problema de permisos): {e}"


def try_read_text(path: str, max_bytes: int):
    """Intenta leer un archivo como texto, para las búsquedas de contenido.

    Devuelve una tupla (texto_o_None, mensaje_de_error_o_None):
      - Si el archivo pesa más que 'max_bytes', se omite intencionadamente
        (no es un error, es una decisión de rendimiento) y se devuelve
        (None, None).
      - Si hay un problema real de lectura (permisos, archivo bloqueado
        por otro proceso, etc.), se devuelve (None, "mensaje de error").
      - Si se lee correctamente, se intenta decodificar primero como UTF-8
        y, si falla, como Latin-1 (que prácticamente nunca falla), para
        cubrir tanto archivos de texto modernos como antiguos.
    """
    try:
        size = os.path.getsize(path)
        if size > max_bytes:
            return None, None  # omitido a propósito por tamaño, no es un error
        with open(path, "rb") as f:
            raw = f.read()
    except (OSError, PermissionError) as e:
        return None, f"No se pudo leer el contenido (posible problema de permisos): {e}"

    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError:
        try:
            return raw.decode("latin-1"), None
        except Exception as e:
            return None, f"No se pudo decodificar el contenido como texto: {e}"


def unique_destination_path(dest_folder: str, filename: str) -> str:
    """Calcula una ruta de destino LIBRE dentro de 'dest_folder' para 'filename'.

    Si ya existe un archivo con ese nombre en la carpeta destino, se añade
    un sufijo numérico incremental (" (1)", " (2)", ...) antes de la
    extensión, de forma que al mover varios archivos con el mismo nombre
    (por ejemplo, duplicados que venían de subcarpetas distintas) NUNCA se
    sobrescribe ni se pierde ninguno de ellos.
    """
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(dest_folder, filename)
    counter = 1
    while os.path.exists(candidate):
        candidate = os.path.join(dest_folder, f"{base} ({counter}){ext}")
        counter += 1
    return candidate


def open_file_location(path: str):
    """Abre el explorador de archivos del sistema operativo en la carpeta
    que contiene 'path', seleccionando el archivo cuando el sistema lo
    permite (Windows y macOS). En Linux simplemente se abre la carpeta,
    ya que no hay una forma universal de "seleccionar" un archivo concreto
    entre los distintos gestores de archivos (Nautilus, Dolphin, etc.)."""
    folder = os.path.dirname(path)
    system = platform.system()
    try:
        if system == "Windows":
            # /select, resalta el archivo dentro del explorador de Windows
            subprocess.run(["explorer", "/select,", os.path.normpath(path)])
        elif system == "Darwin":  # macOS
            subprocess.run(["open", "-R", path])
        else:  # Linux y otros
            subprocess.run(["xdg-open", folder])
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo abrir la ubicación:\n{e}")


# ==========================================================================
# MOTOR DE ESCANEO
# ==========================================================================
# Toda esta sección NO toca la interfaz gráfica directamente: recorre
# carpetas, aplica filtros y calcula duplicados. Se ejecuta dentro de un
# hilo (threading.Thread) lanzado desde la clase App, y se comunica con la
# interfaz mediante una función de "progreso" (progress_cb) y un evento de
# cancelación (cancel_event) que se le pasan por parámetro.
# ==========================================================================

class ScanCancelled(Exception):
    """Excepción interna usada para interrumpir el escaneo en cuanto el
    usuario pulsa 'Cancelar', sin tener que comprobar una bandera en cada
    línea de código: basta con comprobarla en los bucles principales y
    lanzar esta excepción, que se captura una sola vez en el hilo de la GUI."""
    pass


class FileScanner:
    """Recorre las carpetas indicadas aplicando los filtros seleccionados
    por el usuario, y opcionalmente detecta archivos duplicados (por
    tamaño y/o por contenido exacto).

    Esta clase también lleva la cuenta de los ERRORES que se producen al
    intentar leer o procesar archivos y carpetas concretas (por ejemplo,
    permisos denegados), de modo que esos problemas puntuales no detengan
    el análisis general y, en su lugar, queden reflejados como un contador
    de errores junto a cada archivo afectado.
    """

    def __init__(self, root_folders, recursive, filters, combine_mode,
                 max_text_read, progress_cb, cancel_event):
        self.root_folders = root_folders          # Lista de carpetas raíz a analizar
        self.recursive = recursive                 # ¿Incluir subcarpetas?
        self.filters = filters                       # Diccionario con los filtros activos (ver _gather_filters en App)
        self.combine_mode = combine_mode               # "AND" (todos los filtros) u "OR" (cualquiera)
        self.max_text_read = max_text_read               # Límite de bytes para leer contenido como texto
        self.progress_cb = progress_cb                     # Función a la que avisamos del progreso (count, archivo_actual)
        self.cancel_event = cancel_event                     # threading.Event(): si está "set", hay que parar cuanto antes

        # --- Registro de errores por archivo y por carpeta ---------------
        # self.file_errors: { ruta_de_archivo: [ "mensaje de error 1", ... ] }
        # Se rellena cada vez que try_read_text() o file_hash() devuelven un
        # mensaje de error para una ruta concreta. Al final del escaneo, cada
        # archivo que aparezca en los resultados incorpora aquí su lista de
        # errores y su recuento (columna "Errores" de la tabla).
        self.file_errors = {}

        # self.dir_errors: lista de textos describiendo carpetas a las que no
        # se ha podido acceder (por ejemplo, por permisos del sistema
        # operativo). Se muestra como aviso aparte en el resumen final,
        # porque no corresponde a un archivo concreto sino a una carpeta.
        self.dir_errors = []

        # Contador de archivos de los que no se pudieron leer ni siquiera
        # los metadatos básicos (tamaño, fecha) con os.stat(). Estos no
        # pueden mostrarse como fila en la tabla (no tenemos sus datos),
        # así que solo se informa de cuántos hubo en el resumen final.
        self.unreadable_stat_count = 0

    # ----------------------------------------------------------------
    def _record_error(self, path: str, message: str):
        """Añade un mensaje de error a la lista de errores de 'path'.
        Varias partes del escaneo (lectura de contenido, cálculo de hash)
        pueden fallar de forma independiente para el mismo archivo, así
        que se van acumulando en una lista en vez de sobrescribirse."""
        self.file_errors.setdefault(path, []).append(message)

    # ----------------------------------------------------------------
    def _iter_files(self):
        """Generador que va produciendo, uno a uno, las rutas de todos los
        archivos a examinar dentro de las carpetas raíz, respetando la
        opción de "incluir subcarpetas" y registrando como error cualquier
        subcarpeta a la que el sistema operativo deniegue el acceso (en
        vez de simplemente detener el escaneo completo)."""

        def _on_walk_error(exc):
            # os.walk() llama a esta función cuando no puede listar una
            # carpeta (por permisos, por ejemplo) en vez de lanzar la
            # excepción directamente; así el recorrido puede continuar con
            # el resto de carpetas.
            ruta = getattr(exc, "filename", "?")
            self.dir_errors.append(f"No se pudo acceder a la carpeta: {ruta} ({exc})")

        for root_folder in self.root_folders:
            if self.recursive:
                # os.walk recorre la carpeta y todas sus subcarpetas.
                for dirpath, dirnames, filenames in os.walk(root_folder, onerror=_on_walk_error):
                    if self.cancel_event.is_set():
                        raise ScanCancelled()
                    for fn in filenames:
                        yield os.path.join(dirpath, fn)
            else:
                # Sin recursividad: solo los archivos directamente dentro
                # de la carpeta raíz, sin entrar en sus subcarpetas.
                try:
                    for fn in os.listdir(root_folder):
                        full = os.path.join(root_folder, fn)
                        if os.path.isfile(full):
                            yield full
                except (OSError, PermissionError) as e:
                    self.dir_errors.append(f"No se pudo acceder a la carpeta: {root_folder} ({e})")
                    continue

    # ----------------------------------------------------------------
    def _check_filters(self, path, stat_info):
        """Evalúa TODOS los filtros de atributo activos (nombre, extensión,
        tamaño, fecha, contenido...) sobre un único archivo.

        Devuelve una tupla (paso_o_no: bool, motivos: list[str]):
          - 'paso_o_no' indica si el archivo debe incluirse en los
            resultados según el modo de combinación (Y/O).
          - 'motivos' es la lista de descripciones legibles de qué
            filtro(s) concretos ha cumplido (se muestra en la columna
            "Motivo(s)" de la tabla de resultados).

        Cualquier error de lectura que ocurra al comprobar el contenido del
        archivo se registra mediante self._record_error(), pero NO detiene
        la evaluación de los demás filtros: simplemente ese filtro concreto
        se considera "no cumplido" para ese archivo.
        """
        f = self.filters
        name = os.path.basename(path)
        name_noext, ext = os.path.splitext(name)
        results = []   # resultado booleano de cada filtro de atributo activo
        reasons = []   # descripciones legibles de los filtros que sí se cumplieron

        # --- Nombre exacto -------------------------------------------------
        if f.get("nombre_exacto"):
            target = f["nombre_exacto"]
            ok = (name == target) or (not f.get("nombre_exacto_ext") and name_noext == target)
            results.append(ok)
            if ok:
                reasons.append("Nombre exacto")

        # --- Nombre contiene un texto ---------------------------------------
        if f.get("nombre_contiene"):
            target = f["nombre_contiene"]
            hay = name if f.get("nombre_case_sensitive") else name.lower()
            needle = target if f.get("nombre_case_sensitive") else target.lower()
            ok = needle in hay
            results.append(ok)
            if ok:
                reasons.append("Nombre contiene texto")

        # --- Extensión / tipo de archivo -------------------------------------
        if f.get("extensiones"):
            exts = f["extensiones"]
            ok = ext.lower().lstrip(".") in exts
            results.append(ok)
            if ok:
                reasons.append("Extensión coincide")

        # --- Tamaño exacto ----------------------------------------------------
        if f.get("tam_exacto") is not None:
            ok = stat_info.st_size == f["tam_exacto"]
            results.append(ok)
            if ok:
                reasons.append("Tamaño exacto")

        # --- Tamaño en rango ------------------------------------------------------
        if f.get("tam_min") is not None or f.get("tam_max") is not None:
            tmin = f.get("tam_min") if f.get("tam_min") is not None else 0
            tmax = f.get("tam_max") if f.get("tam_max") is not None else float("inf")
            ok = tmin <= stat_info.st_size <= tmax
            results.append(ok)
            if ok:
                reasons.append("Tamaño en rango")

        # --- Fecha de modificación -------------------------------------------------
        if f.get("fecha_desde") is not None:
            ok = datetime.fromtimestamp(stat_info.st_mtime) >= f["fecha_desde"]
            results.append(ok)
            if ok:
                reasons.append("Modificado después")

        if f.get("fecha_hasta") is not None:
            ok = datetime.fromtimestamp(stat_info.st_mtime) <= f["fecha_hasta"]
            results.append(ok)
            if ok:
                reasons.append("Modificado antes")

        # --- Contenido: texto y/o número -------------------------------------------
        # Solo se intenta leer el archivo UNA vez, aunque estén activos los
        # dos filtros de contenido (texto Y número) a la vez, por eficiencia.
        need_content = f.get("contenido_texto") or f.get("contenido_numero")
        if need_content:
            text, err = try_read_text(path, self.max_text_read)
            if err:
                # Fallo real de lectura (permisos, archivo bloqueado...):
                # lo registramos como error de ESTE archivo concreto.
                self._record_error(path, err)
            if text is None:
                # Ya sea por error o porque el archivo era demasiado grande
                # para leerlo como texto, ningún filtro de contenido puede
                # cumplirse para este archivo.
                if f.get("contenido_texto"):
                    results.append(False)
                if f.get("contenido_numero"):
                    results.append(False)
            else:
                if f.get("contenido_texto"):
                    target = f["contenido_texto"]
                    hay = text if f.get("contenido_case_sensitive") else text.lower()
                    needle = target if f.get("contenido_case_sensitive") else target.lower()
                    ok = needle in hay
                    results.append(ok)
                    if ok:
                        reasons.append("Contenido contiene texto")
                if f.get("contenido_numero"):
                    numero = f["contenido_numero"]
                    if f.get("numero_exacto_flag"):
                        # (?<!\d) y (?!\d): el número no debe tener dígitos
                        # pegados ni antes ni después, para no confundir
                        # "123" con una coincidencia parcial dentro de "1234".
                        pattern = r"(?<!\d)" + re.escape(numero) + r"(?!\d)"
                    else:
                        pattern = re.escape(numero)
                    ok = re.search(pattern, text) is not None
                    results.append(ok)
                    if ok:
                        reasons.append("Contenido contiene número")

        # --- Combinar todos los resultados individuales -----------------------------
        if not results:
            # No hay NINGÚN filtro de atributo activo: puede que el usuario
            # solo quiera buscar duplicados. En ese caso este archivo no se
            # incluye aquí; los grupos de duplicados se añaden aparte, en run().
            return False, reasons

        passed = all(results) if self.combine_mode == "AND" else any(results)
        return passed, reasons

    # ----------------------------------------------------------------
    def run(self):
        """Punto de entrada principal del escaneo.

        Devuelve una tupla (matched, total_scanned, dir_errors):
          - matched: lista de diccionarios, uno por cada archivo que ha
            pasado los filtros (o pertenece a un grupo de duplicados),
            con toda la información necesaria para pintar la tabla de
            resultados (incluyendo errores detectados en ese archivo).
          - total_scanned: número total de archivos examinados (hayan
            pasado los filtros o no), para mostrar "X de Y archivos".
          - dir_errors: lista de textos con las carpetas a las que no se
            pudo acceder durante el recorrido.
        """
        matched = []
        total_scanned = 0
        want_dup_exact = self.filters.get("dup_exacto")
        want_dup_size = self.filters.get("dup_tamano")

        # Guardamos (ruta, stat) de TODOS los archivos recorridos, no solo
        # los que superan los filtros de atributo, porque los necesitamos
        # para poder comparar tamaños/hashes entre sí al buscar duplicados
        # (dos archivos pueden ser duplicados aunque ninguno de los dos,
        # por separado, cumpla ningún otro filtro).
        all_files_info = []

        # -------------------- 1) Recorrido + filtros de atributo --------------------
        for path in self._iter_files():
            if self.cancel_event.is_set():
                raise ScanCancelled()
            try:
                stat_info = os.stat(path)
            except (OSError, PermissionError):
                # No se pudieron leer ni los metadatos básicos del archivo.
                # No podemos construir una fila de resultados sin tamaño ni
                # fecha, así que solo lo contamos para el resumen final.
                self.unreadable_stat_count += 1
                continue

            total_scanned += 1
            if total_scanned % 25 == 0:
                # Avisamos a la interfaz cada 25 archivos (no en cada uno,
                # para no saturarla de actualizaciones).
                self.progress_cb(total_scanned, path)

            passed, reasons = self._check_filters(path, stat_info)
            if passed:
                matched.append({
                    "path": path,
                    "name": os.path.basename(path),
                    "size": stat_info.st_size,
                    "mtime": stat_info.st_mtime,
                    "reasons": reasons,
                    "hash": None,
                    "group": "",
                })

            if want_dup_exact or want_dup_size:
                all_files_info.append((path, stat_info))

        self.progress_cb(total_scanned, "Buscando duplicados…" if (want_dup_exact or want_dup_size) else "Finalizando…")

        # -------------------- 2) Duplicados por TAMAÑO --------------------
        if want_dup_size:
            by_size = {}
            for path, stat_info in all_files_info:
                by_size.setdefault(stat_info.st_size, []).append((path, stat_info))
            dup_groups = {sz: lst for sz, lst in by_size.items() if len(lst) > 1}

            existing_paths = {m["path"] for m in matched}
            for sz, lst in dup_groups.items():
                group_label = f"Tamaño duplicado ({human_size(sz)})"
                for path, stat_info in lst:
                    if path in existing_paths:
                        # Ya estaba en resultados por otro filtro: solo añadimos el motivo.
                        for m in matched:
                            if m["path"] == path:
                                m["reasons"].append(group_label)
                                m["group"] = m["group"] or group_label
                    else:
                        matched.append({
                            "path": path,
                            "name": os.path.basename(path),
                            "size": stat_info.st_size,
                            "mtime": stat_info.st_mtime,
                            "reasons": [group_label],
                            "hash": None,
                            "group": group_label,
                        })
                        existing_paths.add(path)

        # -------------------- 3) Duplicados EXACTOS (por hash) --------------------
        if want_dup_exact:
            if self.cancel_event.is_set():
                raise ScanCancelled()

            # Optimización: solo calculamos el hash (operación cara, hay que
            # leer el archivo entero) de archivos cuyo TAMAÑO ya coincide con
            # el de al menos otro archivo. Dos archivos de tamaños distintos
            # nunca pueden tener contenido idéntico, así que ni lo intentamos.
            by_size = {}
            for path, stat_info in all_files_info:
                by_size.setdefault(stat_info.st_size, []).append(path)
            candidates = [p for lst in by_size.values() if len(lst) > 1 for p in lst]

            hashes = {}
            done = 0
            for path in candidates:
                if self.cancel_event.is_set():
                    raise ScanCancelled()
                h, err = file_hash(path)
                done += 1
                if done % 10 == 0:
                    self.progress_cb(total_scanned, f"Calculando hash… {path}")
                if err:
                    self._record_error(path, err)
                if h:
                    hashes.setdefault(h, []).append(path)

            existing_paths = {m["path"] for m in matched}
            for h, paths in hashes.items():
                if len(paths) < 2:
                    continue
                group_label = f"Duplicado exacto (hash {h[:10]}…)"
                for path in paths:
                    stat_info = os.stat(path)  # ya sabemos que es accesible (se pudo hashear)
                    if path in existing_paths:
                        for m in matched:
                            if m["path"] == path:
                                m["hash"] = h
                                if group_label not in m["reasons"]:
                                    m["reasons"].append(group_label)
                                m["group"] = group_label  # el duplicado exacto manda sobre el de tamaño
                    else:
                        matched.append({
                            "path": path,
                            "name": os.path.basename(path),
                            "size": stat_info.st_size,
                            "mtime": stat_info.st_mtime,
                            "reasons": [group_label],
                            "hash": h,
                            "group": group_label,
                        })
                        existing_paths.add(path)

        # -------------------- 4) Adjuntar errores registrados a cada fila --------------------
        # Cada archivo que aparece en 'matched' recibe aquí su lista completa
        # de errores (puede tener más de uno: por ejemplo, fallo al leer su
        # contenido de texto Y fallo al calcular su hash) y el recuento que
        # se muestra en la columna "Errores" de la tabla.
        for m in matched:
            errores = self.file_errors.get(m["path"], [])
            m["errors"] = errores
            m["error_count"] = len(errores)

        return matched, total_scanned, self.dir_errors


# ==========================================================================
# INTERFAZ GRÁFICA
# ==========================================================================

class App(tk.Tk):
    """Ventana principal de la aplicación. Contiene:
      - El panel de selección de carpetas.
      - El panel de filtros (a la izquierda).
      - La tabla de resultados (a la derecha), con su resumen de espacio.
      - La barra de progreso y los botones de acción (analizar, exportar,
        eliminar, mover...).
    """

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1250x800")
        self.minsize(1050, 680)

        self.root_folders = []              # Carpetas añadidas por el usuario
        self.cancel_event = threading.Event()   # Señal compartida con el hilo de escaneo
        self.scan_thread = None                    # Referencia al hilo en curso (si lo hay)
        self.results = []                             # Última lista de resultados (dicts) obtenida

        self._build_style()
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_style(self):
        """Configura un tema visual moderno (ttk 'clam') y algunos estilos
        reutilizados en varios sitios (botón destacado, filas de tabla)."""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass  # si el tema 'clam' no existe en este sistema, seguimos con el que haya
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        # Fila resaltada en rojo suave para archivos con errores detectados
        style.configure("Errores.Treeview", foreground="#b00020")

    # ------------------------------------------------------------------
    def _build_ui(self):
        """Construye toda la disposición de la ventana: carpetas arriba,
        filtros + resultados en el medio, progreso y botones abajo."""
        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)

        # ---------------- Panel superior: carpetas a analizar ----------------
        top = ttk.LabelFrame(outer, text=" Carpetas a analizar ", padding=8)
        top.pack(fill="x", pady=(0, 8))

        self.folders_list = tk.Listbox(top, height=3, selectmode="extended")
        self.folders_list.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btns_folder = ttk.Frame(top)
        btns_folder.pack(side="left")
        ttk.Button(btns_folder, text="Añadir carpeta…", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(btns_folder, text="Quitar seleccionada", command=self.remove_folder).pack(fill="x", pady=2)
        self.recursive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btns_folder, text="Incluir subcarpetas", variable=self.recursive_var).pack(anchor="w", pady=2)

        # ---------------- Panel central: filtros (izq.) + resultados (der.) ----------------
        mid = ttk.Panedwindow(outer, orient="horizontal")
        mid.pack(fill="both", expand=True)

        filters_frame = ttk.LabelFrame(mid, text=" Filtros (combínalos como quieras) ", padding=8)
        results_frame = ttk.LabelFrame(mid, text=" Resultados ", padding=8)
        mid.add(filters_frame, weight=0)
        mid.add(results_frame, weight=1)

        self._build_filters(filters_frame)
        self._build_results(results_frame)

        # ---------------- Panel inferior: progreso, resumen y botones ----------------
        bottom = ttk.Frame(outer, padding=(0, 8, 0, 0))
        bottom.pack(fill="x")

        self.progress = ttk.Progressbar(bottom, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 4))

        self.status_var = tk.StringVar(value="Listo.")
        ttk.Label(bottom, textvariable=self.status_var).pack(anchor="w")

        # Resumen de espacio en disco / errores, se rellena al terminar cada análisis
        self.summary_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=self.summary_var, foreground="#333333",
                  font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        # --- Fila 1 de botones: análisis, exportación y selección ---
        action_bar = ttk.Frame(bottom)
        action_bar.pack(fill="x", pady=(6, 2))

        self.scan_btn = ttk.Button(action_bar, text="▶ Analizar", style="Accent.TButton", command=self.start_scan)
        self.scan_btn.pack(side="left", padx=(0, 6))
        self.cancel_btn = ttk.Button(action_bar, text="■ Cancelar", command=self.cancel_scan, state="disabled")
        self.cancel_btn.pack(side="left", padx=(0, 6))
        ttk.Separator(action_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(action_bar, text="Exportar CSV…", command=self.export_csv).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar, text="Abrir ubicación", command=self.open_selected_location).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar, text="Copiar ruta", command=self.copy_selected_path).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar, text="Ver errores del seleccionado", command=self.show_selected_errors).pack(side="left", padx=(0, 6))
        ttk.Separator(action_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(action_bar, text="Seleccionar todo", command=self.select_all_results).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar, text="Seleccionar solo duplicados", command=self.select_duplicates).pack(side="left", padx=(0, 6))

        # --- Fila 2 de botones: eliminar / mover (individual y por grupos de duplicados) ---
        action_bar2 = ttk.Frame(bottom)
        action_bar2.pack(fill="x", pady=(2, 0))

        ttk.Label(action_bar2, text="Sobre la selección:", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar2, text="🗑 Eliminar seleccionados…", command=self.delete_selected).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar2, text="📁 Mover seleccionados a carpeta…", command=self.move_selected).pack(side="left", padx=(0, 6))
        ttk.Separator(action_bar2, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Label(action_bar2, text="Duplicados (conserva 1 por grupo):", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar2, text="🗑 Eliminar el resto…",
                   command=self.delete_duplicates_keep_first).pack(side="left", padx=(0, 6))
        ttk.Button(action_bar2, text="📁 Mover el resto a carpeta…",
                   command=self.move_duplicates_keep_first).pack(side="left")

    # ------------------------------------------------------------------
    def _build_filters(self, parent):
        """Construye el panel de filtros de la izquierda. Al ser muchos
        campos, va dentro de un Canvas con scroll vertical para que quepan
        todos aunque la ventana no sea muy alta."""
        canvas = tk.Canvas(parent, highlightthickness=0, width=330)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        pad = {"padx": 4, "pady": 3, "sticky": "w"}

        # -- Nombre exacto ----------------------------------------------------
        self.var_nombre_exacto_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Nombre exacto (literal)", variable=self.var_nombre_exacto_on).grid(row=0, column=0, columnspan=2, **pad)
        self.var_nombre_exacto = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_nombre_exacto, width=28).grid(row=1, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")
        self.var_nombre_exacto_ext = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Ignorar extensión al comparar", variable=self.var_nombre_exacto_ext).grid(row=2, column=0, columnspan=2, **pad)

        ttk.Separator(inner).grid(row=3, column=0, columnspan=2, sticky="we", pady=6)

        # -- Nombre contiene ----------------------------------------------------
        self.var_nombre_contiene_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Nombre contiene texto", variable=self.var_nombre_contiene_on).grid(row=4, column=0, columnspan=2, **pad)
        self.var_nombre_contiene = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_nombre_contiene, width=28).grid(row=5, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")
        self.var_nombre_case = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Distinguir mayúsculas/minúsculas", variable=self.var_nombre_case).grid(row=6, column=0, columnspan=2, **pad)

        ttk.Separator(inner).grid(row=7, column=0, columnspan=2, sticky="we", pady=6)

        # -- Extensión ----------------------------------------------------------
        self.var_ext_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Extensión / tipo de archivo", variable=self.var_ext_on).grid(row=8, column=0, columnspan=2, **pad)
        self.var_ext = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_ext, width=28).grid(row=9, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")
        ttk.Label(inner, text="Ej: pdf, jpg, docx (separadas por coma)", foreground="#666").grid(row=10, column=0, columnspan=2, padx=4, sticky="w")

        ttk.Separator(inner).grid(row=11, column=0, columnspan=2, sticky="we", pady=6)

        # -- Contenido: texto -----------------------------------------------------
        self.var_cont_texto_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Contenido contiene texto/palabra", variable=self.var_cont_texto_on).grid(row=12, column=0, columnspan=2, **pad)
        self.var_cont_texto = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_cont_texto, width=28).grid(row=13, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")
        self.var_cont_case = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Distinguir mayúsculas/minúsculas", variable=self.var_cont_case).grid(row=14, column=0, columnspan=2, **pad)

        # -- Contenido: número ------------------------------------------------------
        self.var_cont_num_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Contenido contiene número", variable=self.var_cont_num_on).grid(row=15, column=0, columnspan=2, **pad)
        self.var_cont_num = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_cont_num, width=28).grid(row=16, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")
        self.var_num_exacto = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Número exacto (no parte de otro número)", variable=self.var_num_exacto).grid(row=17, column=0, columnspan=2, **pad)

        ttk.Separator(inner).grid(row=18, column=0, columnspan=2, sticky="we", pady=6)

        # -- Tamaño exacto --------------------------------------------------------
        self.var_tam_exacto_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Tamaño exacto (bytes)", variable=self.var_tam_exacto_on).grid(row=19, column=0, columnspan=2, **pad)
        self.var_tam_exacto = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_tam_exacto, width=28).grid(row=20, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")

        # -- Tamaño en rango -------------------------------------------------------
        self.var_tam_rango_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Tamaño en rango (bytes)", variable=self.var_tam_rango_on).grid(row=21, column=0, columnspan=2, **pad)
        rango_fr = ttk.Frame(inner)
        rango_fr.grid(row=22, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")
        self.var_tam_min = tk.StringVar()
        self.var_tam_max = tk.StringVar()
        ttk.Entry(rango_fr, textvariable=self.var_tam_min, width=12).pack(side="left")
        ttk.Label(rango_fr, text=" a ").pack(side="left")
        ttk.Entry(rango_fr, textvariable=self.var_tam_max, width=12).pack(side="left")

        ttk.Separator(inner).grid(row=23, column=0, columnspan=2, sticky="we", pady=6)

        # -- Fechas ------------------------------------------------------------------
        self.var_fecha_desde_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Modificado después de (AAAA-MM-DD)", variable=self.var_fecha_desde_on).grid(row=24, column=0, columnspan=2, **pad)
        self.var_fecha_desde = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_fecha_desde, width=28).grid(row=25, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")

        self.var_fecha_hasta_on = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Modificado antes de (AAAA-MM-DD)", variable=self.var_fecha_hasta_on).grid(row=26, column=0, columnspan=2, **pad)
        self.var_fecha_hasta = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_fecha_hasta, width=28).grid(row=27, column=0, columnspan=2, padx=4, pady=(0, 2), sticky="we")

        ttk.Separator(inner).grid(row=28, column=0, columnspan=2, sticky="we", pady=6)

        # -- Duplicados -------------------------------------------------------------
        self.var_dup_exacto = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Buscar duplicados EXACTOS (mismo contenido)", variable=self.var_dup_exacto).grid(row=29, column=0, columnspan=2, **pad)
        self.var_dup_tamano = tk.BooleanVar()
        ttk.Checkbutton(inner, text="Buscar archivos con TAMAÑO duplicado", variable=self.var_dup_tamano).grid(row=30, column=0, columnspan=2, **pad)

        ttk.Separator(inner).grid(row=31, column=0, columnspan=2, sticky="we", pady=6)

        # -- Modo de combinación de filtros ------------------------------------------
        ttk.Label(inner, text="Modo de combinación de filtros:", font=("Segoe UI", 9, "bold")).grid(row=32, column=0, columnspan=2, padx=4, pady=(2, 2), sticky="w")
        self.var_combine = tk.StringVar(value="AND")
        ttk.Radiobutton(inner, text="Cumplir TODOS los filtros (Y)", variable=self.var_combine, value="AND").grid(row=33, column=0, columnspan=2, **pad)
        ttk.Radiobutton(inner, text="Cumplir CUALQUIER filtro (O)", variable=self.var_combine, value="OR").grid(row=34, column=0, columnspan=2, **pad)

        ttk.Separator(inner).grid(row=35, column=0, columnspan=2, sticky="we", pady=6)
        ttk.Label(inner, text="Límite lectura de contenido (MB):").grid(row=36, column=0, columnspan=2, padx=4, sticky="w")
        self.var_max_mb = tk.StringVar(value="50")
        ttk.Entry(inner, textvariable=self.var_max_mb, width=10).grid(row=37, column=0, padx=4, pady=(0, 8), sticky="w")

        for c in range(2):
            inner.grid_columnconfigure(c, weight=1)

    # ------------------------------------------------------------------
    def _build_results(self, parent):
        """Construye la tabla (Treeview) donde se listan los archivos
        encontrados, con sus columnas de nombre, ruta, ESPACIO (tamaño),
        fecha, número de ERRORES y motivo(s)."""
        cols = ("name", "path", "size", "mtime", "errors", "reasons")
        self.tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="extended")
        headings = {
            "name": ("Nombre", 170),
            "path": ("Ruta", 330),
            "size": ("Espacio", 90),      # tamaño/espacio que ocupa el archivo en disco
            "mtime": ("Modificado", 130),
            "errors": ("Errores", 70),     # nº de errores detectados al analizar ESTE archivo
            "reasons": ("Motivo(s)", 210),
        }
        for c, (label, width) in headings.items():
            self.tree.heading(c, text=label, command=lambda cc=c: self._sort_by(cc))
            self.tree.column(c, width=width, anchor="w")
        # La columna de errores queda centrada, se lee mejor como número
        self.tree.column("errors", anchor="center")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(parent, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Doble clic sobre una fila -> abrir su ubicación en el explorador
        self.tree.bind("<Double-1>", lambda e: self.open_selected_location())

        # Las filas de archivos con errores se pintan en un color distinto
        # (rojo suave) para que salten a la vista sin tener que leer la
        # columna "Errores" de cada fila una por una.
        self.tree.tag_configure("con_errores", foreground="#b00020")

        self.count_var = tk.StringVar(value="0 resultados")
        ttk.Label(parent, textvariable=self.count_var, font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=(4, 0))

    # ==================================================================
    # Manejo de carpetas
    # ==================================================================
    def add_folder(self):
        """Abre el selector de carpetas del sistema y añade la elegida a
        la lista (evitando duplicarla si ya estaba añadida)."""
        folder = filedialog.askdirectory(title="Selecciona una carpeta")
        if folder and folder not in self.root_folders:
            self.root_folders.append(folder)
            self.folders_list.insert("end", folder)

    def remove_folder(self):
        """Quita de la lista las carpetas seleccionadas en el Listbox."""
        sel = list(self.folders_list.curselection())
        sel.reverse()  # borramos de atrás hacia adelante para no desajustar los índices
        for i in sel:
            self.folders_list.delete(i)
            del self.root_folders[i]

    # ==================================================================
    # Construcción de filtros a partir de lo marcado en la GUI
    # ==================================================================
    def _gather_filters(self):
        """Lee todos los checkboxes/campos del panel de filtros y construye
        el diccionario de filtros que espera FileScanner, validando que los
        datos introducidos tengan sentido (números válidos, fechas con el
        formato correcto, etc.).

        Devuelve (filtros: dict, errores_de_validacion: list[str]).
        """
        f = {}
        errors = []

        if self.var_nombre_exacto_on.get():
            if not self.var_nombre_exacto.get().strip():
                errors.append("Falta el nombre exacto a buscar.")
            f["nombre_exacto"] = self.var_nombre_exacto.get().strip()
            f["nombre_exacto_ext"] = self.var_nombre_exacto_ext.get()

        if self.var_nombre_contiene_on.get():
            if not self.var_nombre_contiene.get().strip():
                errors.append("Falta el texto que debe contener el nombre.")
            f["nombre_contiene"] = self.var_nombre_contiene.get().strip()
            f["nombre_case_sensitive"] = self.var_nombre_case.get()

        if self.var_ext_on.get():
            raw = self.var_ext.get().strip()
            if not raw:
                errors.append("Falta indicar al menos una extensión.")
            exts = {e.strip().lower().lstrip(".") for e in raw.split(",") if e.strip()}
            f["extensiones"] = exts

        if self.var_cont_texto_on.get():
            if not self.var_cont_texto.get().strip():
                errors.append("Falta el texto de contenido a buscar.")
            f["contenido_texto"] = self.var_cont_texto.get()
            f["contenido_case_sensitive"] = self.var_cont_case.get()

        if self.var_cont_num_on.get():
            raw = self.var_cont_num.get().strip()
            if not raw:
                errors.append("Falta el número a buscar en el contenido.")
            elif not re.match(r"^-?\d+(\.\d+)?$", raw):
                errors.append("El número de contenido no es válido.")
            f["contenido_numero"] = raw
            f["numero_exacto_flag"] = self.var_num_exacto.get()

        if self.var_tam_exacto_on.get():
            raw = self.var_tam_exacto.get().strip()
            if not raw.isdigit():
                errors.append("El tamaño exacto debe ser un número entero de bytes.")
            else:
                f["tam_exacto"] = int(raw)

        if self.var_tam_rango_on.get():
            mn = self.var_tam_min.get().strip()
            mx = self.var_tam_max.get().strip()
            if not mn and not mx:
                errors.append("Indica al menos un límite (mínimo o máximo) para el rango de tamaño.")
            if mn:
                if not mn.isdigit():
                    errors.append("El tamaño mínimo debe ser un entero.")
                else:
                    f["tam_min"] = int(mn)
            if mx:
                if not mx.isdigit():
                    errors.append("El tamaño máximo debe ser un entero.")
                else:
                    f["tam_max"] = int(mx)

        if self.var_fecha_desde_on.get():
            raw = self.var_fecha_desde.get().strip()
            try:
                f["fecha_desde"] = datetime.strptime(raw, "%Y-%m-%d")
            except ValueError:
                errors.append("Fecha 'después de' inválida. Usa AAAA-MM-DD.")

        if self.var_fecha_hasta_on.get():
            raw = self.var_fecha_hasta.get().strip()
            try:
                f["fecha_hasta"] = datetime.strptime(raw, "%Y-%m-%d")
            except ValueError:
                errors.append("Fecha 'antes de' inválida. Usa AAAA-MM-DD.")

        f["dup_exacto"] = self.var_dup_exacto.get()
        f["dup_tamano"] = self.var_dup_tamano.get()

        # Al menos un filtro (de atributo o de duplicados) debe estar activo;
        # si no, el escaneo no tendría ningún criterio con el que trabajar.
        active_filters = any([
            self.var_nombre_exacto_on.get(), self.var_nombre_contiene_on.get(),
            self.var_ext_on.get(), self.var_cont_texto_on.get(), self.var_cont_num_on.get(),
            self.var_tam_exacto_on.get(), self.var_tam_rango_on.get(),
            self.var_fecha_desde_on.get(), self.var_fecha_hasta_on.get(),
            f["dup_exacto"], f["dup_tamano"],
        ])
        if not active_filters:
            errors.append("Activa al menos un filtro o una opción de duplicados.")

        return f, errors

    # ==================================================================
    # Escaneo (lanzamiento, hilo de fondo, finalización)
    # ==================================================================
    def start_scan(self):
        """Valida las carpetas y filtros elegidos y lanza el escaneo en un
        hilo de segundo plano, dejando la interfaz totalmente usable
        (barra de progreso animada, botón 'Cancelar' activo) mientras dura."""
        if not self.root_folders:
            messagebox.showwarning("Sin carpetas", "Añade al menos una carpeta para analizar.")
            return

        filters, errors = self._gather_filters()
        if errors:
            messagebox.showerror("Revisa los filtros", "\n".join(f"• {e}" for e in errors))
            return

        try:
            max_mb = float(self.var_max_mb.get().strip() or "50")
        except ValueError:
            max_mb = 50
        max_bytes = int(max_mb * 1024 * 1024)

        # Limpiamos resultados anteriores antes de empezar el nuevo escaneo
        self.tree.delete(*self.tree.get_children())
        self.results = []
        self.count_var.set("Analizando…")
        self.status_var.set("Analizando…")
        self.summary_var.set("")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.scan_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.cancel_event.clear()

        combine_mode = self.var_combine.get()
        recursive = self.recursive_var.get()
        folders = list(self.root_folders)

        def progress_cb(count, current):
            # Esta función se llama desde el HILO de escaneo, así que usamos
            # self.after(0, ...) para que la actualización de la interfaz se
            # ejecute de forma segura en el hilo principal de Tkinter.
            self.after(0, lambda: self.status_var.set(f"Archivos escaneados: {count} — {current}"))

        def worker():
            """Función que se ejecuta en el hilo de fondo: hace todo el
            trabajo pesado (recorrer carpetas, leer archivos, calcular
            hashes) sin bloquear la ventana."""
            scanner = FileScanner(folders, recursive, filters, combine_mode, max_bytes,
                                   progress_cb, self.cancel_event)
            try:
                matched, total, dir_errors = scanner.run()
                self.after(0, lambda: self._on_scan_done(matched, total, dir_errors,
                                                           scanner.unreadable_stat_count, folders))
            except ScanCancelled:
                self.after(0, self._on_scan_cancelled)
            except Exception as e:
                self.after(0, lambda: self._on_scan_error(e))

        self.scan_thread = threading.Thread(target=worker, daemon=True)
        self.scan_thread.start()

    def cancel_scan(self):
        """Pide al hilo de escaneo que se detenga lo antes posible."""
        self.cancel_event.set()
        self.status_var.set("Cancelando…")

    def _on_scan_done(self, matched, total, dir_errors, unreadable_stat_count, folders):
        """Se ejecuta (en el hilo principal) cuando el escaneo termina con
        éxito: vuelca los resultados en la tabla y calcula el resumen de
        espacio en disco / errores."""
        self.progress.stop()
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.results = matched

        archivos_con_error = 0
        for m in matched:
            mtime_str = datetime.fromtimestamp(m["mtime"]).strftime("%Y-%m-%d %H:%M")
            reasons_str = "; ".join(m["reasons"]) if m["reasons"] else "—"
            error_count = m.get("error_count", 0)
            if error_count:
                archivos_con_error += 1
            errors_str = str(error_count) if error_count else "0"
            # Si el archivo tiene errores, pintamos la fila en rojo (tag "con_errores")
            tags = ("con_errores",) if error_count else ()
            self.tree.insert("", "end", iid=m["path"], tags=tags, values=(
                m["name"], m["path"], human_size(m["size"]), mtime_str, errors_str, reasons_str
            ))

        self.count_var.set(f"{len(matched)} resultados de {total} archivos escaneados")
        self.status_var.set("Análisis completado.")

        # ---- Resumen de espacio en disco y errores ----
        self.summary_var.set(self._build_summary_text(matched, dir_errors, unreadable_stat_count, folders))

    def _build_summary_text(self, matched, dir_errors, unreadable_stat_count, folders):
        """Construye el texto de resumen que aparece bajo la barra de
        estado: espacio total de los resultados, espacio recuperable si se
        eliminan los duplicados repetidos, espacio libre en disco de las
        carpetas analizadas, y avisos de errores/carpetas inaccesibles."""
        total_size = sum(m["size"] for m in matched)

        # Espacio "recuperable": suma del tamaño de todos los archivos que
        # son copias repetidas dentro de un grupo de duplicados (es decir,
        # todos menos el primero de cada grupo, que es el que se conservaría).
        groups = {}
        for m in matched:
            if m.get("group"):
                groups.setdefault(m["group"], []).append(m)
        recuperable = 0
        for g, items in groups.items():
            if len(items) > 1:
                recuperable += sum(it["size"] for it in items[1:])

        # Espacio libre en disco: se consulta una vez por cada carpeta raíz
        # distinta (para no repetir si varias carpetas están en el mismo disco).
        discos_vistos = set()
        libres = []
        for folder in folders:
            libres_bytes, libres_txt = get_disk_free_space(folder)
            if libres_txt is None:
                continue
            clave = os.path.splitdrive(os.path.abspath(folder))[0] or folder
            if clave in discos_vistos:
                continue
            discos_vistos.add(clave)
            libres.append(f"{folder} → {libres_txt} libres")

        partes = [
            f"Espacio total de los resultados: {human_size(total_size)}",
        ]
        if recuperable:
            partes.append(f"Espacio recuperable en duplicados: {human_size(recuperable)}")
        if libres:
            partes.append("Espacio libre: " + " | ".join(libres))

        errores_con = sum(1 for m in matched if m.get("error_count"))
        if errores_con:
            partes.append(f"⚠ {errores_con} archivo(s) con errores detectados")
        if unreadable_stat_count:
            partes.append(f"⚠ {unreadable_stat_count} archivo(s) no se pudieron leer en absoluto")
        if dir_errors:
            partes.append(f"⚠ {len(dir_errors)} carpeta(s) inaccesible(s)")

        return "   •   ".join(partes)

    def _on_scan_cancelled(self):
        """Se ejecuta cuando el usuario cancela el escaneo a mitad de camino:
        deja en la tabla lo que se hubiera encontrado hasta ese momento."""
        self.progress.stop()
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Análisis cancelado por el usuario.")
        self.count_var.set(f"{len(self.tree.get_children())} resultados (parcial)")

    def _on_scan_error(self, e):
        """Se ejecuta si ocurre un error inesperado (no controlado) durante
        el escaneo; se informa al usuario en vez de cerrar la aplicación."""
        self.progress.stop()
        self.scan_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Error durante el análisis.")
        messagebox.showerror("Error", str(e))

    # ==================================================================
    # Ordenar columnas de la tabla
    # ==================================================================
    def _sort_by(self, col):
        """Reordena las filas de la tabla al hacer clic en una cabecera.
        Para la columna de tamaño se ordena por el valor numérico real
        (bytes), no por el texto formateado ("2.0 KB" ordenaría mal como
        texto frente a "500 B")."""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def keyfunc(pair):
            val = pair[0]
            if col == "size":
                for m in self.results:
                    if m["path"] == pair[1]:
                        return m["size"]
                return 0
            if col == "errors":
                for m in self.results:
                    if m["path"] == pair[1]:
                        return m.get("error_count", 0)
                return 0
            return val.lower() if isinstance(val, str) else val

        items.sort(key=keyfunc)
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

    # ==================================================================
    # Selección rápida
    # ==================================================================
    def _selected_paths(self):
        """Devuelve la lista de rutas actualmente seleccionadas en la tabla."""
        return list(self.tree.selection())

    def select_all_results(self):
        """Selecciona todas las filas de la tabla de una vez."""
        children = self.tree.get_children()
        if not children:
            messagebox.showinfo("Sin resultados", "Todavía no hay resultados para seleccionar.")
            return
        self.tree.selection_set(children)
        self.status_var.set(f"{len(children)} archivo(s) seleccionados.")

    def select_duplicates(self):
        """Selecciona en la tabla todos los archivos que pertenecen a algún
        grupo de duplicados (útil antes de pulsar 'Mover el resto' o
        revisar manualmente qué duplicados hay)."""
        dup_paths = [m["path"] for m in self.results if m.get("group")]
        if not dup_paths:
            messagebox.showinfo("Sin duplicados", "No hay archivos marcados como duplicados en los resultados.")
            return
        self.tree.selection_set(dup_paths)
        self.status_var.set(f"{len(dup_paths)} archivo(s) duplicados seleccionados.")

    # ==================================================================
    # Acciones varias sobre resultados
    # ==================================================================
    def open_selected_location(self):
        """Abre en el explorador del sistema la carpeta del primer archivo
        seleccionado (resaltándolo, si el sistema operativo lo permite)."""
        sel = self._selected_paths()
        if not sel:
            messagebox.showinfo("Selecciona algo", "Selecciona un archivo en la tabla primero.")
            return
        open_file_location(sel[0])

    def copy_selected_path(self):
        """Copia al portapapeles la(s) ruta(s) de los archivos seleccionados,
        una por línea, útil para pegarlas en otro programa."""
        sel = self._selected_paths()
        if not sel:
            messagebox.showinfo("Selecciona algo", "Selecciona un archivo en la tabla primero.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(sel))
        self.status_var.set(f"{len(sel)} ruta(s) copiada(s) al portapapeles.")

    def show_selected_errors(self):
        """Muestra en una ventana emergente el detalle completo de los
        mensajes de error registrados para el/los archivo(s) seleccionado(s),
        ya que la tabla solo muestra el NÚMERO de errores por espacio."""
        sel = self._selected_paths()
        if not sel:
            messagebox.showinfo("Selecciona algo", "Selecciona un archivo en la tabla primero.")
            return

        bloques = []
        for path in sel:
            m = next((x for x in self.results if x["path"] == path), None)
            if not m:
                continue
            errores = m.get("errors", [])
            if errores:
                detalle = "\n".join(f"  - {e}" for e in errores)
                bloques.append(f"{m['name']}:\n{detalle}")

        if not bloques:
            messagebox.showinfo("Sin errores", "El/los archivo(s) seleccionado(s) no tienen errores registrados.")
            return

        messagebox.showwarning("Detalle de errores", "\n\n".join(bloques))

    def export_csv(self):
        """Exporta la tabla completa de resultados a un archivo CSV
        (separado por ';' para que Excel en español lo abra bien de forma
        directa), incluyendo el espacio ocupado y los errores de cada
        archivo."""
        if not self.results:
            messagebox.showinfo("Sin resultados", "No hay resultados para exportar todavía.")
            return
        path = filedialog.asksaveasfilename(
            title="Guardar como CSV", defaultextension=".csv",
            filetypes=[("Archivo CSV", "*.csv")], initialfile="resultados_analisis.csv"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Nombre", "Ruta", "Espacio (bytes)", "Espacio legible",
                                  "Modificado", "Hash SHA-256", "Nº errores", "Detalle errores", "Motivo(s)"])
                for m in self.results:
                    row = [
                        m["name"], m["path"], m["size"], human_size(m["size"]),
                        datetime.fromtimestamp(m["mtime"]).strftime("%Y-%m-%d %H:%M:%S"),
                        m["hash"] or "", m.get("error_count", 0),
                        " | ".join(m.get("errors", [])), "; ".join(m["reasons"]),
                    ]
                    writer.writerow([csv_safe_cell(value) for value in row])
            messagebox.showinfo("Exportado", f"Resultados exportados a:\n{path}")
        except Exception as e:
            messagebox.showerror("Error al exportar", str(e))

    # ==================================================================
    # Eliminar
    # ==================================================================
    def delete_selected(self):
        """Elimina PERMANENTEMENTE (no a la papelera) los archivos
        seleccionados en la tabla, tras confirmación explícita del usuario."""
        sel = self._selected_paths()
        if not sel:
            messagebox.showinfo("Selecciona algo", "Selecciona uno o varios archivos primero.")
            return
        if not messagebox.askyesno(
                "Confirmar borrado",
                f"Vas a eliminar PERMANENTEMENTE {len(sel)} archivo(s).\n\n¿Seguro que quieres continuar?"):
            return
        self._process_paths(sel, mode="delete")

    def delete_duplicates_keep_first(self):
        """Para cada grupo de duplicados detectado, conserva el primer
        archivo del grupo en su ubicación original y elimina el resto."""
        to_delete = self._duplicates_minus_first()
        if not to_delete:
            messagebox.showinfo("Nada que eliminar",
                                 "No hay grupos de duplicados en los resultados actuales.")
            return
        if not messagebox.askyesno(
                "Confirmar borrado de duplicados",
                f"Se conservará 1 archivo por grupo de duplicados y se eliminarán "
                f"PERMANENTEMENTE {len(to_delete)} archivo(s) repetido(s).\n\n"
                f"¿Continuar?"):
            return
        self._process_paths(to_delete, mode="delete")

    # ==================================================================
    # Mover a carpeta
    # ==================================================================
    def move_selected(self):
        """Mueve los archivos seleccionados a una carpeta que elige el
        usuario. Si ya existe un archivo con el mismo nombre en destino,
        se renombra automáticamente (ver unique_destination_path) para no
        perder ni sobrescribir ningún archivo."""
        sel = self._selected_paths()
        if not sel:
            messagebox.showinfo("Selecciona algo", "Selecciona uno o varios archivos primero.")
            return
        dest = filedialog.askdirectory(title="Selecciona la carpeta de destino")
        if not dest:
            return
        if not messagebox.askyesno(
                "Confirmar movimiento",
                f"Vas a mover {len(sel)} archivo(s) a:\n{dest}\n\n"
                f"Si ya existe un archivo con el mismo nombre en esa carpeta, "
                f"se renombrará automáticamente para no sobrescribirlo ni perderlo.\n\n"
                f"¿Continuar?"):
            return
        self._process_paths(sel, mode="move", dest_folder=dest)

    def move_duplicates_keep_first(self):
        """Para cada grupo de duplicados, conserva el primer archivo donde
        está y mueve el resto a la carpeta que elijas, renombrando
        automáticamente si el nombre ya existe allí. Útil para juntar todos
        los duplicados en una carpeta de revisión antes de decidir si
        borrarlos definitivamente."""
        to_move = self._duplicates_minus_first()
        if not to_move:
            messagebox.showinfo("Nada que mover",
                                 "No hay grupos de duplicados en los resultados actuales.")
            return
        dest = filedialog.askdirectory(title="Selecciona la carpeta destino para los duplicados")
        if not dest:
            return
        if not messagebox.askyesno(
                "Confirmar movimiento de duplicados",
                f"Se conservará 1 archivo por grupo de duplicados en su sitio, y se moverán "
                f"{len(to_move)} archivo(s) repetido(s) a:\n{dest}\n\n"
                f"Si el nombre ya existe en destino, se renombrará automáticamente "
                f"(no se borrará ni se sobrescribirá nada).\n\n¿Continuar?"):
            return
        self._process_paths(to_move, mode="move", dest_folder=dest)

    # ==================================================================
    # Helpers compartidos por las acciones de eliminar / mover
    # ==================================================================
    def _duplicates_minus_first(self):
        """Devuelve las rutas de cada grupo de duplicados EXCEPTO la
        primera de cada grupo (esa primera es la que se conserva en su
        ubicación original en todas las acciones de 'conservar 1 por grupo')."""
        groups = {}
        for m in self.results:
            if m.get("group"):
                groups.setdefault(m["group"], []).append(m["path"])
        to_process = []
        for g, paths in groups.items():
            if len(paths) > 1:
                to_process.extend(paths[1:])  # conserva el primero de cada grupo
        return to_process

    def _process_paths(self, paths, mode, dest_folder=None):
        """Aplica 'delete' o 'move' a una lista de rutas, de forma segura:
        si un archivo concreto falla (por permisos, por estar en uso, etc.)
        se anota el error y se continúa con el resto, en vez de abortar
        toda la operación. Al mover, si el nombre ya existe en destino, se
        renombra automáticamente para no reemplazar ni perder nada."""
        done, failed = 0, []
        for p in paths:
            try:
                if mode == "delete":
                    os.remove(p)
                elif mode == "move":
                    target = unique_destination_path(dest_folder, os.path.basename(p))
                    shutil.move(p, target)
                done += 1
                if self.tree.exists(p):
                    self.tree.delete(p)
                self.results = [m for m in self.results if m["path"] != p]
            except Exception as e:
                failed.append((p, str(e)))

        self.count_var.set(f"{len(self.tree.get_children())} resultados")
        verbo = "Eliminados" if mode == "delete" else "Movidos"
        msg = f"{verbo}: {done}"
        if failed:
            msg += f"\nFallidos: {len(failed)}\n" + "\n".join(f"{p}: {err}" for p, err in failed[:10])
        titulo = "Resultado del borrado" if mode == "delete" else "Resultado del movimiento"
        messagebox.showinfo(titulo, msg)


# ==========================================================================
# PUNTO DE ENTRADA
# ==========================================================================

def main():
    """Crea la ventana principal y arranca el bucle de eventos de Tkinter.
    Esta es la función que se ejecuta al lanzar el script directamente, y
    también la que PyInstaller empaqueta como punto de arranque del .exe."""
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
