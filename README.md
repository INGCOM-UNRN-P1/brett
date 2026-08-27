# 📏 BRETT — Auditor de Padding y Alineación de Estructuras C

BRETT analiza la disposición en memoria (`Memory Layout`) de tipos de datos compuestos (`typedef struct`) en C, calcula los bytes de relleno (`padding`) desperdiciados por desalineación de campos y genera sugerencias automáticas de reordenamiento para minimizar el tamaño de las estructuras.

## Uso Rápido

```bash
# 1. Auditar estructuras en archivos C o cabeceras H
brett audit src/ main.h

# 2. Generar sugerencias de layout optimizado
brett optimize tipos.h

# 3. Salida estructurada JSON
brett audit src/ --json
```
