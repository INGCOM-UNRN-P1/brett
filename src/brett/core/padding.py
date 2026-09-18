"""Motor de análisis de alineación y optimización de padding en BRETT usando Tree-Sitter AST."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node

from brett.core.models import CampoStruct, ReportePadding, StructInfo
from brett.core.preprocesador import enmascarar_bloques_inactivos

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

    # Se resuelve por token exacto, no por substring: "long" es substring de
    # "long double", así que el matching ingenuo (`if k in tipo`) le asignaba
    # a `long double` el tamaño de `long` (8 B en vez de 16 B en x86_64).
    # "long double" es la única combinación que no se puede resolver token a
    # token, porque tanto "long" como "double" son, cada uno por separado,
    # una clave válida de TIPO_INFO con el tamaño equivocado.
    tokens = tipo_limpio.replace(",", " ").split()
    if "long" in tokens and "double" in tokens:
        return (16, 16)

    for token in tokens:
        if token in ("const", "volatile", "unsigned", "signed"):
            continue
        if token in TIPO_INFO:
            return TIPO_INFO[token]

    return (4, 4)  # Fallback estándar


def _analizar_dimensiones_array(decl_node: Node) -> Tuple[int, str, bool]:
    """Recorre los `array_declarator` anidados de un declarador de campo.

    Devuelve (cantidad_de_elementos, sufijo_en_C, hay_dimension_no_resuelta).
    Para un campo escalar devuelve (1, "", False). Las dimensiones se recorren
    de afuera hacia adentro (`int m[3][4]` expone primero el 4), por eso el
    sufijo se arma invirtiendo lo recolectado.
    """
    dimensiones: List[str] = []
    elementos = 1
    no_resuelta = False

    actual: Optional[Node] = decl_node
    while actual is not None:
        if actual.type == "parenthesized_declarator":
            # `char (*pa)[4]` — puntero a arreglo: las dimensiones pertenecen al
            # apuntado, no al campo. El campo ocupa un puntero y no se multiplica.
            sufijo_fuente = "".join(f"[{d}]" for d in reversed(dimensiones))
            return 1, sufijo_fuente, False

        if actual.type == "array_declarator":
            size_node = actual.child_by_field_name("size")
            if size_node is None:
                # `int v[]` — miembro flexible: no aporta bytes al sizeof.
                dimensiones.append("")
                elementos *= 0
            else:
                texto = size_node.text.decode("utf-8", errors="replace").strip()
                dimensiones.append(texto)
                if size_node.type == "number_literal":
                    try:
                        elementos *= int(texto, 0)
                    except ValueError:
                        no_resuelta = True
                else:
                    # Dimensión simbólica (`int v[MAX]`): no se puede resolver sin
                    # expandir el preprocesador; se marca en vez de asumir 1.
                    no_resuelta = True

        actual = actual.child_by_field_name("declarator")

    sufijo = "".join(f"[{d}]" for d in reversed(dimensiones))
    return elementos, sufijo, no_resuelta


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

                if type_node.type == "struct_specifier" and type_node.child_by_field_name("body") is not None:
                    # Campo que es a su vez un struct (anónimo o nombrado) con
                    # cuerpo propio: su tamaño real depende de SUS campos, no
                    # de una tabla de tipos primitivos. Sin este caso, el
                    # fallback genérico (4, 4) devolvía 4 B para un struct que
                    # podía ocupar muchos más, corriendo mal todos los offsets
                    # siguientes.
                    interno = analizar_struct_node(type_node, f"{nombre_campo}_anidado", archivo, f.start_point.row + 1)
                    if interno is not None:
                        tam_elemento = interno.tamanio_total_bytes
                        align = max((c.alineacion for c in interno.campos), default=1)
                    else:
                        tam_elemento, align = _obtener_tamanio_alineacion(tipo_raw)
                else:
                    tam_elemento, align = _obtener_tamanio_alineacion(tipo_raw)

                elementos, sufijo_array, dim_no_resuelta = _analizar_dimensiones_array(decl_node)
                # Un arreglo ocupa N veces su elemento pero conserva la
                # alineación del elemento (C11 §6.2.8).
                tam = tam_elemento * elementos

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
                    sufijo_array=sufijo_array,
                    dimension_no_resuelta=dim_no_resuelta,
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
        nota = " [dimensión no resuelta]" if c.dimension_no_resuelta else ""
        codigo_opt += f"    {c.declaracion};  // {c.tamanio} B (offset {c.offset_optimizado}){nota}\n"
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
    # El contenido de un `#if 0` no se compila: enmascararlo evita
    # reportar hallazgos sobre código deliberadamente desactivado.
    contenido = enmascarar_bloques_inactivos(contenido)
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
            try:
                todas.extend(analizar_archivo_c(p))
            except Exception:
                continue
        elif p.is_dir():
            for sub in p.rglob("*"):
                if sub.is_file() and sub.suffix.lower() in (".c", ".h"):
                    try:
                        todas.extend(analizar_archivo_c(sub))
                    except Exception:
                        continue

    return ReportePadding(structs=todas)
