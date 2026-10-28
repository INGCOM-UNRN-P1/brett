"""Motor de layout de structs de C: el único del ecosistema (revisión 07, brett y kane).

`disponer` ubica cada campo en el primer offset múltiplo de su alineación y redondea el total a
la mayor alineación (C11 §6.7.2.1 y §6.2.8). brett lo usa para medir el padding y el orden
óptimo; kane, para leer registros de un archivo binario con los mismos offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class Elemento:
    nombre: str
    offset: int
    tamanio: int
    es_relleno: bool = False


def disponer(campos: Sequence[Tuple[str, int, int]]) -> Tuple[List[Elemento], int]:
    """Los campos `(nombre, tamaño, alineación)` en orden, con el relleno entre ellos y al final.

    Devuelve los elementos (campos y rellenos `_pad_<offset>` / `_tail_pad_<offset>`) y el
    tamaño total del struct (al menos 1)."""
    elementos: List[Elemento] = []
    offset = 0
    max_align = 1
    for nombre, tamanio, alineacion in campos:
        alineacion = max(1, alineacion)
        max_align = max(max_align, alineacion)
        if offset % alineacion:
            relleno = alineacion - offset % alineacion
            elementos.append(Elemento(f"_pad_{offset}", offset, relleno, True))
            offset += relleno
        elementos.append(Elemento(nombre, offset, tamanio))
        offset += tamanio
    if offset % max_align:
        relleno = max_align - offset % max_align
        elementos.append(Elemento(f"_tail_pad_{offset}", offset, relleno, True))
        offset += relleno
    return elementos, max(offset, 1)



# ── Tipos primitivos por ABI (Ola 18) ─────────────────────────────────────────────────────────
#
# El tamaño y la alineación de cada tipo primitivo, por ABI. Es la única tabla del ecosistema:
# brett la usa para medir el padding, y kane y bishop para leer y dibujar los mismos offsets.
# x86_64, aarch64 y riscv64 en Linux son LP64 y coinciden en los tipos primitivos (difieren en el
# signo de `char`, que no cambia el layout); las diferencias que importan en P1 son Windows
# (LLP64: `long` de 4 bytes, el entorno MSYS2 UCRT64 de los estudiantes) e i386 (ILP32: punteros de
# 4 bytes y `double` alineado a 4).

ABI_POR_OMISION = "x86_64"

_LP64: Dict[str, Tuple[int, int]] = {
    "char": (1, 1), "bool": (1, 1), "short": (2, 2), "int": (4, 4), "long": (8, 8), "long long": (8, 8),
    "float": (4, 4), "double": (8, 8), "long double": (16, 16), "pointer": (8, 8), "size_t": (8, 8),
    "ssize_t": (8, 8), "ptrdiff_t": (8, 8), "intptr_t": (8, 8), "uintptr_t": (8, 8), "wchar_t": (4, 4),
    "int8_t": (1, 1), "uint8_t": (1, 1), "int16_t": (2, 2), "uint16_t": (2, 2), "int32_t": (4, 4),
    "uint32_t": (4, 4), "int64_t": (8, 8), "uint64_t": (8, 8),
}

ABIS: Dict[str, Dict[str, Tuple[int, int]]] = {
    "x86_64": dict(_LP64),
    "aarch64": dict(_LP64),
    "riscv64": dict(_LP64),
    # gcc de MinGW-w64 (MSYS2 UCRT64): LLP64, `long double` de 80 bits guardado en 16 bytes.
    "x86_64-windows": {**_LP64, "long": (4, 4), "wchar_t": (2, 2)},
    # System V i386: ILP32 y los tipos de 8 bytes alineados a 4.
    "i386": {**_LP64, "long": (4, 4), "long long": (8, 4), "double": (8, 4), "long double": (12, 4),
             "pointer": (4, 4), "size_t": (4, 4), "ssize_t": (4, 4), "ptrdiff_t": (4, 4), "intptr_t": (4, 4),
             "uintptr_t": (4, 4), "int64_t": (8, 4), "uint64_t": (8, 4)},
}

_CALIFICADORES = {"const", "volatile", "unsigned", "signed", "static", "register", "restrict", "struct", "enum"}


class AbiDesconocida(ValueError):
    pass


def tipo_canonico(tipo: str) -> str:
    """`unsigned long int` → `long`, `const char *` → `pointer`, `_Bool` → `bool`, `enum dia` → `int`."""
    texto = tipo.strip()
    if "*" in texto:
        return "pointer"
    tokens = [t for t in texto.replace(",", " ").split()]
    if tokens and tokens[0] == "enum":
        return "int"
    tokens = [("bool" if t == "_Bool" else t) for t in tokens if t not in _CALIFICADORES]
    if tokens.count("long") >= 2:
        return "long long"
    if "long" in tokens and "double" in tokens:
        return "long double"
    if not tokens:  # `unsigned` o `signed` solos son `int`
        return "int"
    for t in tokens:
        if t in _LP64:
            return t
    return tokens[-1]


def tamanio_alineacion(tipo: str, abi: str = ABI_POR_OMISION) -> Tuple[int, int]:
    """(tamaño, alineación) de un tipo primitivo en esa ABI; (4, 4) si no es primitivo (un typedef
    que no se conoce), como antes."""
    if abi not in ABIS:
        raise AbiDesconocida(f"ABI desconocida '{abi}'; usá {', '.join(ABIS)}.")
    return ABIS[abi].get(tipo_canonico(tipo), (4, 4))
