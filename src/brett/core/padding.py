"""Motor de análisis de alineación y optimización de padding en BRETT usando Tree-Sitter AST."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node

from brett.core.models import CampoStruct, ReportePadding, StructInfo

_C_LANGUAGE: Optional[Language] = None
_PARSER: Optional[Parser] = None


def get_c_parser() -> Parser:
    global _C_LANGUAGE, _PARSER
    if _PARSER is None:
        _C_LANGUAGE = Language(tsc.language())
        _PARSER = Parser(_C_LANGUAGE)
    return _PARSER


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


def _find_identifier(node: Node) -> Optional[str]:
    if node.type in ("identifier", "type_identifier", "field_identifier"):
        return node.text.decode("utf-8", errors="replace")
    for child in node.children:
        if child.type in ("identifier", "type_identifier", "field_identifier"):
            return child.text.decode("utf-8", errors="replace")
        elif child.type in ("pointer_declarator", "array_declarator", "parenthesized_declarator"):
            res = _find_identifier(child)
            if res:
                return res
    return None


def analizar_struct_node(node: Node, nombre: str, archivo: Path, linea: int) -> Optional[StructInfo]:
    """Analiza los campos de un nodo struct AST, calcula el padding y sugiere el orden óptimo."""
    body_node = node.child_by_field_name("body")
    if not body_node:
        return None

    campos: List[CampoStruct] = []
    offset = 0
    max_align = 1
    tamanio_datos = 0

    for f in body_node.children:
        if f.type == "field_declaration":
            type_node = f.child_by_field_name("type")
            decl_node = f.child_by_field_name("declarator")
            if not decl_node and len(f.children) >= 2:
                decl_node = f.children[1]

            if type_node and decl_node:
                tipo_raw = type_node.text.decode("utf-8", errors="replace").strip()
                nombre_campo = _find_identifier(decl_node) or "campo"
                if "*" in decl_node.text.decode("utf-8", errors="replace"):
                    tipo_raw += " *"

                tam, align = _obtener_tamanio_alineacion(tipo_raw)
                if align > max_align:
                    max_align = align

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

    tamanio_total = offset
    if max_align > 0 and tamanio_total % max_align != 0:
        tamanio_total += max_align - (tamanio_total % max_align)

    padding_desperdiciado = tamanio_total - tamanio_datos

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
    """Extrae y audita todas las estructuras definidas en un archivo C o H usando Tree-Sitter AST."""
    archivo = Path(archivo)
    if not archivo.is_file():
        return []

    contenido = archivo.read_text(encoding="utf-8", errors="ignore")
    source_bytes = contenido.encode("utf-8")
    parser = get_c_parser()
    tree = parser.parse(source_bytes)

    structs: List[StructInfo] = []

    def _traverse(node: Node) -> None:
        if node.type == "type_definition":
            type_node = node.child_by_field_name("type")
            decl_node = node.child_by_field_name("declarator")
            nombre = _find_identifier(decl_node) if decl_node else "AnonStruct"
            if type_node and type_node.type == "struct_specifier":
                linea = node.start_point.row + 1
                s_info = analizar_struct_node(type_node, nombre, archivo, linea)
                if s_info:
                    structs.append(s_info)
                return

        elif node.type == "struct_specifier" and node.parent and node.parent.type == "declaration":
            name_node = node.child_by_field_name("name")
            nombre = name_node.text.decode("utf-8", errors="replace") if name_node else "struct_anon"
            linea = node.start_point.row + 1
            s_info = analizar_struct_node(node, nombre, archivo, linea)
            if s_info:
                structs.append(s_info)
            return

        for child in node.children:
            _traverse(child)

    _traverse(tree.root_node)
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
