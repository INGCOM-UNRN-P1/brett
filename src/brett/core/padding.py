"""Motor de análisis de alineación y optimización de padding en BRETT."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from brett.core.models import CampoStruct, ReportePadding, StructInfo

# Tamaños y alineaciones estándar en x86_64
TIPO_INFO: Dict[str, Tuple[int, int]] = {
    "char": (1, 1),
    "bool": (1, 1),
    "int8_t": (1, 1),
    "uint8_t": (1, 1),
    "short": (2, 2),
    "int16_t": (2, 2),
    "uint16_t": (2, 2),
    "int": (4, 4),
    "float": (4, 4),
    "int32_t": (4, 4),
    "uint32_t": (4, 4),
    "size_t": (8, 8),
    "long": (8, 8),
    "double": (8, 8),
    "int64_t": (8, 8),
    "uint64_t": (8, 8),
    "pointer": (8, 8),
}


def _obtener_tamanio_alineacion(tipo: str) -> Tuple[int, int]:
    tipo_limpio = tipo.strip()
    if "*" in tipo_limpio:
        return TIPO_INFO["pointer"]
    for k, v in TIPO_INFO.items():
        if k in tipo_limpio:
            return v
    return (4, 4)  # Fallback estándar


def analizar_struct(nombre: str, cuerpo: str, archivo: Path, linea: int) -> StructInfo:
    """Analiza los campos de un struct, calcula el padding y sugiere el orden óptimo."""
    campos: List[CampoStruct] = []
    lineas = cuerpo.splitlines()

    re_campo = re.compile(r"^\s*([a-zA-Z0-9_* ]+?)\s+([a-zA-Z0-9_]+)\s*;")

    offset = 0
    max_align = 1
    tamanio_datos = 0

    for l in lineas:
        m = re_campo.search(l)
        if m:
            tipo_raw = m.group(1).strip()
            nombre_campo = m.group(2).strip()

            tam, align = _obtener_tamanio_alineacion(tipo_raw)
            if align > max_align:
                max_align = align

            # Alinear offset al múltiplo de 'align'
            if offset % align != 0:
                offset += align - (offset % align)

            campos.append(CampoStruct(
                tipo=tipo_raw,
                nombre=nombre_campo,
                tamanio=tam,
                alineacion=align,
                offset_original=offset,
            ))

            offset += tam
            tamanio_datos += tam

    # Alinear tamaño total del struct al múltiplo del miembro con mayor alineación
    tamanio_total = offset
    if max_align > 0 and tamanio_total % max_align != 0:
        tamanio_total += max_align - (tamanio_total % max_align)

    padding_desperdiciado = tamanio_total - tamanio_datos

    # Calcular orden optimizado: ordenar campos por alineación descendente
    campos_opt = sorted(campos, key=lambda c: c.alineacion, reverse=True)
    offset_opt = 0
    for c in campos_opt:
        if offset_opt % c.alineacion != 0:
            offset_opt += c.alineacion - (offset_opt % c.alineacion)
        c.offset_optimizado = offset_opt
        offset_opt += c.tamanio

    tamanio_opt = offset_opt
    if max_align > 0 and tamanio_opt % max_align != 0:
        tamanio_opt += max_align - (tamanio_opt % max_align)

    bytes_ahorrados = max(0, tamanio_total - tamanio_opt)

    # Generar código sugerido optimizado
    codigo_opt = f"typedef struct {{\n"
    for c in campos_opt:
        codigo_opt += f"    {c.tipo} {c.nombre};  // {c.tamanio} B (offset {c.offset_optimizado})\n"
    codigo_opt += f"}} {nombre}; // Tamaño optimizado: {tamanio_opt} B (ahorro: {bytes_ahorrados} B)"

    return StructInfo(
        nombre=nombre,
        archivo=archivo,
        linea=linea,
        campos=campos,
        tamanio_total_bytes=tamanio_total,
        tamanio_datos_utiles_bytes=tamanio_datos,
        bytes_padding_desperdiciados=padding_desperdiciado,
        tamanio_optimizado_bytes=tamanio_opt,
        bytes_ahorrados=bytes_ahorrados,
        codigo_optimizado=codigo_opt,
    )


def analizar_archivo_c(archivo: Path) -> List[StructInfo]:
    """Extrae y audita todas las estructuras definidas en un archivo C o H."""
    archivo = Path(archivo)
    if not archivo.is_file():
        return []

    contenido = archivo.read_text(encoding="utf-8", errors="ignore")
    re_struct = re.compile(r"typedef\s+struct\s*(?:[a-zA-Z0-9_]*)\s*\{([^}]+)\}\s*([a-zA-Z0-9_]+)\s*;", re.MULTILINE)

    structs = []
    for m in re_struct.finditer(contenido):
        cuerpo = m.group(1)
        nombre = m.group(2)
        linea = contenido[:m.start()].count("\n") + 1
        s_info = analizar_struct(nombre, cuerpo, archivo, linea)
        structs.append(s_info)

    return structs


def auditar_rutas(rutas: List[Path]) -> ReportePadding:
    """Audita una lista de archivos o directorios."""
    todas: List[StructInfo] = []
    for r in rutas:
        p = Path(r)
        if p.is_file() and p.suffix.lower() in (".c", ".h"):
            todas.extend(analizar_archivo_c(p))
        elif p.is_dir():
            for sub in p.rglob("*"):
                if sub.is_file() and sub.suffix.lower() in (".c", ".h"):
                    todas.extend(analizar_archivo_c(sub))

    return ReportePadding(structs=todas)
