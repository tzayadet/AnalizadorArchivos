# Analizador de Archivos PRO

**Showcase source:** [docs/index.html](docs/index.html) · GitHub Pages deployment is ready but requires enabling Pages in repository settings.

[![Python syntax check](https://github.com/tzayadet/AnalizadorArchivos/actions/workflows/python-syntax.yml/badge.svg)](https://github.com/tzayadet/AnalizadorArchivos/actions/workflows/python-syntax.yml)

Herramienta de escritorio para buscar, filtrar y detectar archivos duplicados
en una o varias carpetas, combinando múltiples criterios a la vez.

No necesita ninguna librería externa: usa solo la librería estándar de
Python (`tkinter`, `hashlib`, `os`, `csv`...), así que funciona en Windows,
macOS y Linux sin instalar nada adicional para ejecutarla desde código fuente.

---

## 1. Qué puede buscar

Puedes activar y combinar (a la vez) cualquiera de estos filtros:

| Filtro | Qué hace |
|---|---|
| **Nombre exacto** | Coincidencia literal del nombre de archivo (con opción de ignorar la extensión) |
| **Nombre contiene** | El nombre incluye un texto/palabra determinada |
| **Extensión / tipo** | Filtra por una o varias extensiones (`pdf, jpg, docx`…) |
| **Contenido contiene texto** | Busca una palabra o frase dentro del contenido del archivo |
| **Contenido contiene número** | Busca un número dentro del contenido (con opción de "número exacto", es decir que no forme parte de otro número mayor) |
| **Tamaño exacto** | El archivo pesa exactamente X bytes |
| **Tamaño en rango** | El archivo pesa entre un mínimo y un máximo (en bytes) |
| **Modificado después / antes de** | Filtra por fecha de última modificación |
| **Duplicados exactos** | Archivos con el **mismo contenido** (comparación por hash SHA-256) |
| **Tamaño duplicado** | Archivos que **pesan exactamente lo mismo**, aunque el contenido sea distinto |

Puedes elegir si los filtros activos deben cumplirse **todos a la vez** (modo
"Y") o si basta con que se cumpla **cualquiera de ellos** (modo "O").

## 2. Qué información se muestra de cada archivo

Además de nombre, ruta y fecha, cada fila de la tabla incluye:

- **Espacio**: el tamaño que ocupa el archivo en disco (ej. `2.3 MB`).
- **Errores**: el número de problemas detectados al intentar analizar ESE
  archivo en concreto (por ejemplo, permisos denegados al leer su contenido
  o al calcular su hash). Si un archivo tiene 1 o más errores, su fila se
  resalta en rojo para que salte a la vista. Puedes ver el texto completo
  de esos errores seleccionando el archivo y pulsando **"Ver errores del
  seleccionado"**.

Justo debajo de la tabla aparece un **resumen de espacio en disco** tras
cada análisis, con:
- Espacio total ocupado por todos los resultados encontrados.
- Espacio "recuperable" si eliminas los duplicados repetidos (conservando
  1 copia de cada grupo).
- Espacio libre actualmente en el/los disco(s) de las carpetas analizadas.
- Avisos si hay archivos con errores o carpetas a las que no se pudo acceder
  (por ejemplo, por permisos del sistema).

## 3. Qué puedes hacer con los resultados

- Ver nombre, ruta completa, tamaño, fecha de modificación y el motivo por el
  que cada archivo aparece en la lista.
- Ordenar la tabla haciendo clic en cualquier cabecera de columna.
- **Exportar a CSV** (compatible con Excel), incluyendo espacio y errores.
- **Abrir la ubicación** del archivo en el explorador del sistema (doble clic
  en una fila, o botón "Abrir ubicación").
- **Copiar la ruta** al portapapeles.
- **Ver errores del seleccionado**: muestra el texto completo de los errores
  detectados en un archivo (la tabla solo muestra el número, por espacio).
- **Seleccionar todo** o **seleccionar solo los duplicados** con un clic (para
  no tener que ir marcando fila a fila con Ctrl/Shift).
- **Eliminar** los archivos seleccionados (con confirmación explícita). El borrado es permanente: no utiliza la Papelera de reciclaje de Windows ni una papelera equivalente.
- **Mover los archivos seleccionados a una carpeta** que tú elijas. Si en esa
  carpeta ya existe un archivo con el mismo nombre, el programa **lo renombra
  automáticamente** (`archivo (1).txt`, `archivo (2).txt`...) para que nunca
  se borre ni se sobrescriba nada, aunque muevas varios archivos con el mismo
  nombre procedentes de carpetas distintas.
- **Sobre los grupos de duplicados**, dos acciones dedicadas que siempre
  conservan 1 copia por grupo en su ubicación original:
  - **Eliminar el resto**: borra permanentemente todas las copias repetidas excepto la primera. Revisa los grupos antes de confirmar.
  - **Mover el resto a una carpeta**: en vez de borrarlas, las mueve a una
    carpeta de tu elección (por ejemplo, una carpeta "Duplicados" para
    revisarlas antes de decidir), con el mismo renombrado automático
    anti-colisión explicado arriba.
- Cancelar un análisis en curso en cualquier momento (botón "Cancelar").

> 💡 Todas las acciones de eliminar/mover muestran un resumen final con
> cuántos archivos se procesaron correctamente y cuáles fallaron (por ejemplo,
> por falta de permisos), sin detener el proceso a mitad de camino.

El escaneo corre en un hilo aparte para que la ventana nunca se quede
congelada, incluso con miles de archivos.

## 4. Ejecutar desde código fuente (cualquier sistema operativo)

Requiere Python 3.8 o superior (Tkinter suele venir incluido; en Linux, si
falta, instálalo con `sudo apt install python3-tk`).

```bash
python analizador_archivos.py
```

## 5. Generar el .exe portable y standalone (solo Windows)

El archivo `build_exe.bat` automatiza todo el proceso. Debes ejecutarlo **en
un PC con Windows** (el .exe de Windows no se puede generar desde Linux/Mac):

1. Instala Python en Windows si no lo tienes: https://www.python.org/downloads/
   — durante la instalación, marca la casilla **"Add Python to PATH"**.
2. Copia estos archivos en Windows en la misma carpeta:
   - `analizador_archivos.py`
   - `build_exe.bat`
3. Haz doble clic en `build_exe.bat`.
4. El script automáticamente:
   - crea un entorno virtual aislado (`venv_build`) para no tocar tu Python
     del sistema,
   - instala PyInstaller,
   - genera un único ejecutable `.exe` (modo `--onefile --windowed`),
   - construye en un directorio temporal independiente y lo elimina al terminar;
   - conserva los directorios y archivos preexistentes del proyecto;
   - evita sobrescribir ejecutables: si ya existe el nombre, genera una variante numerada.
5. Al terminar, encontrarás tu ejecutable en:

   ```
   dist\AnalizadorDeArchivosPRO.exe
   ```

Ese `.exe` es **portable y standalone**: puedes copiarlo a un pendrive o a
cualquier otro PC Windows y funcionará sin instalar Python ni ninguna
dependencia (todo va empaquetado dentro del propio ejecutable).

### Notas sobre el .exe generado

- Pesará entre ~15 y 30 MB, ya que incluye un intérprete de Python completo.
- El primer arranque puede tardar 1-2 segundos más que las siguientes veces
  (PyInstaller descomprime en una carpeta temporal al vuelo).
- Si el antivirus de Windows (Defender u otro) lo marca como sospechoso,
  es un falso positivo muy común con ejecutables generados por PyInstaller;
  puedes añadir una excepción o compilarlo tú mismo con este script para
  verificar el origen del binario.
- Si quieres darle un icono personalizado, añade `--icon=tu_icono.ico` a la
  línea `pyinstaller ...` dentro de `build_exe.bat`.

## 6. Rendimiento con carpetas muy grandes

- La detección de "duplicados exactos" solo calcula el hash de archivos que
  ya comparten tamaño con al menos otro archivo (optimización que evita
  hashear todo el disco).
- La búsqueda de texto/número dentro del contenido tiene un límite de tamaño
  configurable (por defecto 50 MB) para no intentar leer vídeos, instaladores
  u otros binarios enormes como si fueran texto. Puedes cambiarlo desde la
  propia interfaz.
- Si un archivo o carpeta concreto da error (permisos denegados, archivo
  bloqueado por otro programa, enlace roto...), el análisis **no se detiene**:
  ese problema queda registrado como error de ese archivo (o de esa carpeta,
  si es un problema de acceso a nivel de directorio) y el resto del análisis
  continúa con normalidad.
