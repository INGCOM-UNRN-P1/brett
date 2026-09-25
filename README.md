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
```
