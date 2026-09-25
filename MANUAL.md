# Manual de Uso y Referencia Técnica: brett

> **BRETT** — Auditor de alineación y padding de estructuras C y optimizador de reordenamiento de campos
> **Versión:** `0.1.0` · **CLI principal:** `brett` · **Plugin Ripley:** `padding`

---

## 1. Arquitectura y Propósito Pedagógico

`brett` forma parte del ecosistema de herramientas de la cátedra de Programación 1 (UNRN). Su objetivo central es resolver de forma modular, determinista y automatizada las tareas asociadas a su dominio específico dentro del ciclo de desarrollo, evaluación y aprendizaje de software en C.

### Alcance Funcional (Qué cubre)
- Auditoría estática y cálculo del layout de memoria de `typedef struct` en C.
- Determinación de offsets de cada campo, tamaño total del tipo y requerimientos de alineación (`alignof`).
- Identificación y cuantificación de bytes de padding desperdiciados por desalineación de campos.
- Generación de propuestas de reordenamiento óptimo de campos para minimizar el consumo de memoria.

### Límites de Responsabilidad y Delegación (Qué no cubre)
- Decodificación de archivos binarios estructurados en disco con endianness específico (delegado a `kane`).
- Auditoría de visibilidad y ABI en bibliotecas compartidas (delegado a `parker`).
- Publicación directa en servidor LSP en vivo (delegado a `ripley`).

### Principios de Diseño
- **Enfoque Pedagógico:** Diagnósticos y mensajes en español rioplatense orientados a facilitar la comprensión de errores conceptuales.
- **Salida Estructurada Dual:** Soporte nativo para visualización enriquecida en terminal (Rich) y salida parseable para orquestadores (`--json`).
- **Integración Contractual:** Capacidad de emitir secciones de reporte para `dredd` (`dredd-section`) y actuar como satélite orquestado por `ripley`.
- **Idempotencia y Robustez:** Validación de precondiciones y comandos de autodiagnóstico (`doctor`) para verificación del entorno.

---

## 2. Instalación y Requisitos

### Requisitos del Sistema
- **Python:** `>= 3.10` (recomendado Python 3.11 o 3.12).
- **Gestor de paquetes:** [`uv`](https://github.com/astral-sh/uv) (entorno estándar de cátedra).
- **Toolchain C (si aplica):** GCC / Clang, Make, GDB y bibliotecas estándar de desarrollo.

### Instalación en el Entorno de Usuario
Para instalar la herramienta de forma global y aislada en el sistema mediante `uv tool`:
```bash
uv tool install --editable /home/mrtin/dev/tools/brett
```

### Verificación de Instalación
Ejecutá el comando `doctor` para constatar que todas las dependencias y binarios requeridos estén presentes y operativos:
```bash
brett doctor
```

---

## 3. Guía Integral de Comandos (CLI)

| Comando | Descripción Breve |
| :--- | :--- |
| [`brett audit`](#audit) | Audita estructuras en busca de bytes de memoria desperdiciados por desalineación y padding. |
| [`brett report`](#report) | Genera directamente la sección de reporte Markdown de BRETT para Dredd. |
| [`brett optimize`](#optimize) | Genera el código C optimizado reordenando los campos de mayor a menor alineación. |
| [`brett doctor`](#doctor) | Verifica el estado del entorno de auditoría de memoria y padding BRETT (Tree-Sitter C, Python, GCC). |

### `brett audit`

Audita estructuras en busca de bytes de memoria desperdiciados por desalineación y padding.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `rutas` | `List[Path]` | Archivos C/H o directorios a auditar. |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--json` | `bool` | `False` | Emitir reporte en JSON. |
| `--md`, `--output-md`, `-o` | `Optional[Path]` | `None` | Generar sección de reporte en formato Markdown para fusión en Dredd. |

#### Ejemplo de Invocación
```bash
brett audit <rutas>
```

### `brett report`

Genera directamente la sección de reporte Markdown de BRETT para Dredd.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `rutas` | `List[Path]` | Archivos C/H o directorios a auditar. |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--output`, `-o` | `Optional[Path]` | `None` | Ruta de destino del archivo Markdown. |

#### Ejemplo de Invocación
```bash
brett report <rutas>
```

### `brett optimize`

Genera el código C optimizado reordenando los campos de mayor a menor alineación.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `archivo` | `Path` | Archivo C/H con las estructuras a optimizar. |

#### Ejemplo de Invocación
```bash
brett optimize <archivo>
```

### `brett doctor`

Verifica el estado del entorno de auditoría de memoria y padding BRETT (Tree-Sitter C, Python, GCC).

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--json` | `bool` | `False` | Emitir diagnóstico en formato JSON estructurado. |

#### Ejemplo de Invocación
```bash
brett doctor
```

---

## 4. Formatos de Salida e Integración con el Ecosistema

### Modo Interactivo / Terminal (Rich)
Por defecto, la herramienta renderiza paneles, árboles y tablas estilizadas para facilitar la lectura del estudiante y docente en terminales modernas con soporte ANSI.

### Modo Estructurado JSON (`--json`)
Para integración con pipelines de CI/CD, scripts de automatización u orquestadores externos, la opción `--json` emite un documento JSON estricto por la salida estándar (`stdout`), dirigiendo cualquier mensaje de logging a `stderr`:
```bash
brett audit --json
```

### Integración con Dredd (`dredd-section`)
Cuando la herramienta genera reportes de evaluación para entregas de alumnos, produce una sección Markdown estandarizada conforme al contrato de integración de Dredd (v1.0.0):
```markdown
<!-- dredd-section: brett, tool=brett, version=0.1.0, status=ok -->
```
Este encabezado garantiza la agregación determinista de los hallazgos en la rúbrica docente.

### Integración con Ripley
`brett` está registrada en el catálogo de plugins satélites de Ripley (`SATELLITE_CATALOG`). Puede invocarse directamente a través del motor de evaluación de Ripley configurando el análisis en `ripley.toml`.

---

## 5. Diagnóstico y Códigos de Salida

### Códigos de Retorno (`exit code`)
| Código | Significado |
| :---: | :--- |
| `0` | Ejecución exitosa sin hallazgos críticos ni errores de sintaxis. |
| `1` | Hallazgos pedagógicos detectados, infracción de reglas o advertencias activas. |
| `2` | Error de sintaxis en argumentos CLI o archivo fuente no encontrado. |
| `>2` | Error no recuperable del sistema, fallo de memoria o excepción interna. |

### Diagnóstico del Entorno (`doctor`)
Ante comportamientos inesperados, verificá el estado operativo con:
```bash
brett doctor
```
Comprueba la presencia de las dependencias requeridas y la integridad de los componentes del paquete.