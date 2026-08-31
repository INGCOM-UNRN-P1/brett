---
title: "Manual de Referencia: brett"
subtitle: "Brett — Auditor de Memoria, Padding y Layout Óptimo de Structs en C"
author: "Cátedra de Algoritmos y Programación"
date: "2026-08-31"
---

(manual-brett)=
# Brett — Auditor de Memoria, Padding y Layout Óptimo de Structs en C

````{abstract}
**Rol en el ecosistema:** Auditoría de alineación de memoria, cálculo de bytes desperdiciados por padding y reordenamiento automático de campos.
````

---

(manual-brett-proposito)=
## 1. Propósito y Filosofía Pedagógica

La herramienta **`brett`** forma parte del ecosistema oficial de software de la cátedra. Su diseño sigue principios pedagógicos rigurosos:

1. **Evidencia Técnica Directa**: Todo diagnóstico se fundamenta en la norma ISO C (C11/C23), en el modelo de memoria del sistema o en convenciones arquitectónicas formales.
2. **Acción Correctiva Concreta**: Cada advertencia incluye la prescripción técnica inmediata para resolver el defecto sin recurrir a conjeturas.
3. **Autonomía del Estudiante**: Facilita la autoevaluación local antes de la entrega final del trabajo práctico.
4. **Objetividad Docente**: Estandariza la corrección automática eliminando discrepancias subjetivas en la evaluación.

---

(manual-brett-instalacion)=
## 2. Instalación y Diagnóstico del Entorno

````{important}
Asegurate de contar con el compilador GCC/Clang y las librerías del sistema instaladas antes de ejecutar `brett`.
````

Para comprobar el estado de salud de tu entorno de trabajo y las dependencias auxiliares:

````{code-block} bash
# Comprobación de dependencias del sistema
brett doctor
````

Si se detecta la falta de alguna utilidad (como `gdb`, `valgrind`, `clang-format` o `typst`), el comando indicará el paquete exacto a instalar según tu distribución GNU/Linux o entorno MSYS2.

---

(manual-brett-comandos)=
## 3. Referencia Completa de Comandos CLI

A continuación se detallan los subcomandos principales disponibles en `brett`:

| Sintaxis del Comando | Descripción y Efecto |
| :--- | :--- |
| `brett audit <archivo.h>` | Analiza las structs del header y reporta bytes de padding. |
| `brett optimize <archivo.h>` | Reordena campos de mayor a menor para minimizar el tamaño total. |
| `brett diff <archivo.h>` | Muestra la comparativa de tamaño antes y después en terminal. |
| `brett diagram <struct_name> -f <archivo.h>` | Dibuja el mapa de bytes y huecos de padding en ASCII. |

````{tip}
Podés agregar el flag `--json` a la mayoría de los comandos para exportar resultados en formato estructurado o `--md` para generar reportes Markdown para el informe de entrega.
````

---

(manual-brett-tutorial)=
## 4. Tutorial Paso a Paso con Ejemplos Reales

### Caso de Estudio

Considerá el siguiente fragmento de código representativo:

````{code-block} c
:linenos:
// Struct con 10 bytes de padding en arquitectura de 64 bits
struct PaqueteDesalineado {
    char tipo;         // 1 byte (+ 3 padding)
    int id;            // 4 bytes
    char estado;       // 1 byte (+ 7 padding)
    double timestamp;  // 8 bytes
}; // Total: 24 bytes (desperdicio: 41.6%)
````

### Ejecución de la Herramienta

Ejecutá el análisis desde tu terminal:

````{code-block} bash
brett audit <archivo.h>
````

### Salida Obtenida en Consola

````{code-block} text
Struct: struct PaqueteDesalineado (Tamaño: 24 bytes | Padding: 10 bytes)
Layout en memoria (64-bit):
[ tipo (1B) ][ PAD (3B) ][    id (4B)    ]
[ estado (1B) ][        PAD (7B)        ]
[           timestamp (8B)              ]

Propuesta de optimización (Tamaño: 16 bytes | Ahorro: 33.3%):
1. double timestamp; (8 bytes)
2. int id;           (4 bytes)
3. char tipo;        (1 byte)
4. char estado;      (1 byte + 2B pad final)
````

````{note}
Prestá atención a la explicación pedagógica generada: la herramienta no solo señala la línea del problema, sino que explica la causa raíz y el impacto en memoria o arquitectura.
````

---

(manual-brett-ejercicios)=
## 5. Ejercicios Prácticos y Desafíos

Practicá el uso avanzado de **`brett`** resolviendo los siguientes ejercicios:

````{exercise} Desafío 1: Auditoría de Header de Red
Auditar `include/protocolo.h` y detectar structs con más de 20% de padding.

**Instrucción de ejecución:**
```bash
brett audit include/protocolo.h
```
````

````{solution} Desafío 1
```bash
brett audit include/protocolo.h
# Verificá que la operación concluya exitosamente con código de salida 0.
```
````

````{exercise} Desafío 2: Optimización Automática In-Place
Aplicar reordenamiento óptimo sobre `include/envio.h`.

**Instrucción de ejecución:**
```bash
brett optimize include/envio.h --in-place
```
````

````{solution} Desafío 2
```bash
brett optimize include/envio.h --in-place
# Revisá el archivo generado o el informe en terminal para confirmar la resolución del problema.
```
````

````{exercise} Desafío 3: Comparativa Multiplataforma 32 vs 64 bits
Evaluar la diferencia de alineación entre x86 y ARM.

**Instrucción de ejecución:**
```bash
brett audit include/nodo.h --arch 32bit --arch 64bit
```
````

````{solution} Desafío 3
```bash
brett audit include/nodo.h --arch 32bit --arch 64bit
# Comprobá que la salida confirme la ausencia de advertencias o errores pendientes.
```
````

---

(manual-brett-makefile)=
## 6. Integración en el Flujo de Trabajo y Makefile

Para incorporar `brett` de forma automática a tu flujo de desarrollo, agregá la siguiente regla en el `Makefile` de tu proyecto:

````{code-block} makefile
check-brett:
	@echo "=== Ejecutando verificación con brett ==="
	brett check src/ include/

.PHONY: check-brett
````

Ejecutá `make check-brett` antes de cada commit para asegurar que tu código conserve el estado de aprobación.

---

(manual-brett-arquitectura)=
## 7. Arquitectura Interna y Mecanismo Técnico

La herramienta **`brett`** implementa un motor de alta precisión basado en:

- **Tecnología Núcleo:** `libclang / C-Parser AST + ABI Memory Layout Calculator (x86_64 / ARM64 / ILP32)`.
- **Aislamiento y Determinismo:** Diseñada para operar sin efectos colaterales en entornos de integración continua (CI), terminales de estudiantes y servidores docentes headless.
- **Manejo de Errores Pedagógico:** Todo fallo de sintaxis, memoria o lógica se traduce en una acción prescriptiva concreta con su respectiva justificación técnica.

---

(manual-brett-ecosistema)=
## 8. Integración y Conexión con el Ecosistema

````{note}
Ninguna herramienta opera de forma aislada. **`brett`** forma parte del pipeline integral de evaluación, verificación y enseñanza de la cátedra.
````

### Diagrama de Flujo e Interoperabilidad

````{mermaid}
graph TD
    SRC[Headers C: Structs] --> BRT[Brett: Auditor de Padding]
    BRT -->|Cálculo de Desperdicio| ABI[Modelo de Memoria 64/32-bit]
    BRT -->|Struct Reordenada| GAFF[Gaff: Formateo y Estilo]
    BRT -->|Layout Optimizado| FERRO[Ferro: Perfilador de Caché]
    BRT -->|Esquema de Bytes| KANE[Kane: Mapeo de Archivos Binarios]
````

### Matriz de Intercambio de Datos

| Canal | Herramientas Conectadas | Tipo de Datos Transferidos |
| :--- | :--- | :--- |
| **Entradas (Inputs)** | - `Headers C (.h) desarrollados por estudiantes o cátedra` | Código fuente, AST, binarios, testcases, contratos |
| **Salidas (Outputs)** | - `gaff (formato Allman)`
- `kane (mapeo de archivos binarios)`
- `bishop (mapa de memoria)` | Informes Markdown, diagnósticos Rich, JSON, actas |
| **Sincronización** | `ferro`, `crowe`, `kane` | Validación cruzada, flags compartidos y autofix |

### Pipeline de Integración Recomendado

Podés encadenar `brett` con otras herramientas del ecosistema en una única línea de comando:

````{code-block} bash
# Pipeline de integración típico
brett optimize include/tda.h --in-place && gaff format include/tda.h
````

