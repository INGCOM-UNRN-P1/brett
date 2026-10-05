# 📏 BRETT — Auditor de Padding y Alineación de Estructuras C

> 📖 **Manual de Usuario:** Para una guía exhaustiva de comandos, banderas, arquitectura y ejemplos, consultá el [Manual de Uso](MANUAL.md).

BRETT analiza la disposición en memoria (`Memory Layout`) de tipos de datos compuestos (`typedef struct`) en C, calcula los bytes de relleno (`padding`) desperdiciados por desalineación de campos y genera sugerencias automáticas de reordenamiento para minimizar el tamaño de las estructuras.

---

## 🎯 Alcance

### Qué cubre
- Auditoría estática y cálculo del layout de memoria de `typedef struct` en C.
- Determinación de offsets de cada campo, tamaño total del tipo y requerimientos de alineación (`alignof`).
- Identificación y cuantificación de bytes de padding desperdiciados por desalineación de campos.
- Generación de propuestas de reordenamiento óptimo de campos para minimizar el consumo de memoria.

### Qué no cubre (Límites y Delegación)
- Decodificación de archivos binarios estructurados en disco con endianness específico (delegado a `kane`).
- Auditoría de visibilidad y ABI en bibliotecas compartidas (delegado a `parker`).
- Publicación directa en servidor LSP en vivo (delegado a `ripley`).

---

## 📋 Requisitos

### Requisitos de Sistema y Entorno
- Multiplataforma (Linux, Windows, macOS). Python >= 3.10.

### Dependencias Externas y Binarios
- Ninguno obligatorio (análisis estático basado en AST Tree-Sitter).

### Integración en el Ecosistema
- CLI `brett`. Plugin registrado en `ripley.plugins` bajo el identificador `padding`.

---

## Uso Rápido

```bash
# 1. Auditar estructuras en archivos C o cabeceras H
brett audit src/ main.h

# 2. Generar sugerencias de layout optimizado
brett optimize tipos.h

# 3. Generar reporte consolidado Markdown
brett report src/

# 4. Salida estructurada JSON
brett audit src/ --json

# 5. En el CI de una actividad: fallar solo si reordenando se ahorran 16 bytes o más
brett audit src/ --fail-on 16
```

El cálculo de offsets y relleno (`brett.core.layout.disponer`) es el único del ecosistema: kane lo
usa para leer los registros de un archivo binario con los mismos offsets que reporta brett.

<!-- p1:referencia:inicio — generado por p1-tools/scripts/readme_generado.py: no editar a mano -->

## Referencia rápida

### Requisitos

- Python ≥ 3.11 y [uv](https://docs.astral.sh/uv/getting-started/installation/).

### Comandos

| Comando | Descripción |
|:--|:--|
| `brett audit` | Audita estructuras en busca de bytes de memoria desperdiciados por desalineación y padding. |
| `brett report` | Genera directamente la sección de reporte Markdown de BRETT para Dredd. |
| `brett optimize` | Genera el código C optimizado reordenando los campos de mayor a menor alineación. |
| `brett doctor` | Verifica el estado del entorno de auditoría de memoria y padding BRETT (Tree-Sitter C, Python, GCC). |

Ayuda de cada comando: `brett <comando> -h`.

### Salida JSON

Con `--json`, estos comandos emiten el resultado como JSON por la salida estándar, para usarlo desde scripts, ripley o dredd: `brett audit`, `brett doctor`. El de `doctor --json` lleva `schema_version` y `ok`.

### Códigos de salida

| Código | Significado |
|:--|:--|
| `0` | Terminó bien (en `doctor`: está todo lo requerido). |
| `1` | El comando encontró problemas (hallazgos, pruebas que fallan, un umbral que no se alcanza) o un dato no se pudo usar (un archivo ilegible, un formato inválido). |
| `2` | Error de uso: comando, opción o argumento inválido. |

<!-- p1:referencia:fin -->
