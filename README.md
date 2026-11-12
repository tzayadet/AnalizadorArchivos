# Analizador de Archivos PRO

[![Python syntax check](https://github.com/tzayadet/AnalizadorArchivos/actions/workflows/python-syntax.yml/badge.svg)](https://github.com/tzayadet/AnalizadorArchivos/actions/workflows/python-syntax.yml)

**Project showcase:** [Open the project page](https://tzayadet.github.io/AnalizadorArchivos/) · [Source](docs/index.html)

Herramienta de escritorio para buscar, filtrar y detectar archivos duplicados en una o varias carpetas. Permite combinar criterios, analizar el espacio ocupado y exportar resultados.

## Funcionalidades

- Búsqueda por nombre, extensión, contenido, tamaño y fechas.
- Combinación de filtros mediante condiciones AND/OR.
- Detección de duplicados exactos mediante SHA-256.
- Resumen de espacio ocupado y potencialmente recuperable.
- Registro de errores de acceso y análisis.
- Exportación de resultados a CSV.
- Apertura de ubicaciones, copia de rutas y movimiento de archivos con nombres anti-colisión.

## Requisitos y ejecución

Python 3.10 o superior. Tkinter suele incluirse con las distribuciones estándar de Python.

```bash
python analizador_archivos.py
```

En Windows también puedes utilizar `build_exe.bat` para generar un ejecutable con PyInstaller.

## Seguridad de operaciones

Las acciones de eliminación son permanentes y no utilizan la Papelera de reciclaje. Revisa los archivos seleccionados antes de confirmar. Para una operación reversible, utiliza primero la función de mover archivos a otra carpeta.

La detección por hash identifica contenido idéntico; no demuestra que un archivo sea seguro o auténtico.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Showcase

La página de presentación es un índice informativo; la aplicación de escritorio no se ejecuta en el navegador. Para publicarla, activa GitHub Pages en **Settings → Pages → Build and deployment → Source → GitHub Actions**. Después ejecuta el workflow **Deploy project showcase to GitHub Pages** desde Actions.

## Licencia

Consulta [LICENSE](LICENSE).
