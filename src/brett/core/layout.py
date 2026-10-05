"""Motor de layout de structs de C: el único del ecosistema (revisión 07, brett y kane).

`disponer` ubica cada campo en el primer offset múltiplo de su alineación y redondea el total a
la mayor alineación (C11 §6.7.2.1 y §6.2.8). brett lo usa para medir el padding y el orden
óptimo; kane, para leer registros de un archivo binario con los mismos offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple


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

