<p align="center">
  <img src="https://img.shields.io/badge/DESKTOP_UTILITY-FILE_ANALYZER-101010?style=for-the-badge&labelColor=050805&color=00FF41" alt="File Analyzer"/>
  <img src="https://img.shields.io/badge/PYTHON-WINDOWS_%2F_DESKTOP-101010?style=for-the-badge&logo=python&logoColor=00FF41" alt="Python"/>
</p>

# File Analyzer

Herramienta de escritorio para buscar, filtrar y analizar archivos en una o varias carpetas. Combina criterios de búsqueda, detecta duplicados exactos y permite exportar resultados.

<p align="center">
  <a href="https://tzayadet.github.io/AnalizadorArchivos/"><strong>PROJECT SHOWCASE ↗</strong></a> ·
  <a href="https://github.com/tzayadet/AnalizadorArchivos"><strong>SOURCE CODE</strong></a>
</p>

[![Python syntax check](https://github.com/tzayadet/AnalizadorArchivos/actions/workflows/python-syntax.yml/badge.svg)](https://github.com/tzayadet/AnalizadorArchivos/actions/workflows/python-syntax.yml)

> La página de GitHub Pages es una ficha de presentación; la aplicación de escritorio requiere Python y no se ejecuta en el navegador.

## Features

- Búsqueda por nombre, extensión, contenido, tamaño y fechas.
- Combinación de filtros mediante condiciones AND/OR.
- Detección de duplicados exactos mediante SHA-256.
- Resumen de espacio ocupado y potencialmente recuperable.
- Registro de errores de acceso y análisis.
- Exportación de resultados a CSV.
- Apertura de ubicaciones y copia de rutas.
- Movimiento de archivos con nombres anti-colisión.

## Run locally

**Requirements:** Python 3.10+. Tkinter suele estar incluido en las distribuciones estándar de Python.

```bash
python analizador_archivos.py
```

En Windows, `build_exe.bat` permite generar un ejecutable mediante PyInstaller.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Project layout

| Path | Purpose |
|---|---|
| `analizador_archivos.py` | Aplicación de escritorio |
| `docs/` | Showcase estático |
| `tests/` | Pruebas automatizadas |
| `.github/workflows/` | Validaciones y publicación |

## File operations and safety

Las acciones de eliminación son permanentes y no utilizan la Papelera de reciclaje. Revisa los elementos seleccionados antes de confirmar. Para una operación reversible, utiliza primero la función de mover archivos.

La coincidencia SHA-256 identifica contenido idéntico; no demuestra que un archivo sea seguro o auténtico.

## Deployment

El workflow de Pages está preparado. La publicación de la ficha estática requiere habilitar GitHub Pages con GitHub Actions en la configuración del repositorio. La aplicación requiere Python y un entorno de escritorio compatible.

## License

See [LICENSE](LICENSE).
