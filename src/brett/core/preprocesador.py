"""Enmascarado de bloques de preprocesador inactivos (`#if 0`).

Tree-Sitter no ejecuta el preprocesador: parsea el contenido de un `#if 0`
como si fuera código vivo. Sin enmascararlo, una función peligrosa, una macro
o un struct desactivados a propósito se auditan como si estuvieran activos, y
el estudiante recibe un hallazgo sobre código que no se compila.

El contenido se reemplaza por espacios en vez de borrarse, de modo que los
offsets y los números de línea del original se mantienen intactos.
"""

from __future__ import annotations

import re
from typing import Optional

_INICIO_IF_FALSO = re.compile(r"^\s*#\s*if\s+0\s*(?://.*|/\*.*)?$")
_INICIO_CONDICIONAL = re.compile(r"^\s*#\s*(if|ifdef|ifndef)\b")
_FIN_CONDICIONAL = re.compile(r"^\s*#\s*endif\b")
_RAMA_ALTERNATIVA = re.compile(r"^\s*#\s*(else|elif)\b")


def _blanquear(texto: str) -> str:
    """Sustituye cada carácter por un espacio, conservando los saltos de línea."""
    return "".join("\n" if c == "\n" else " " for c in texto)


def enmascarar_bloques_inactivos(contenido: str) -> str:
    """Blanquea el cuerpo de los bloques `#if 0`, incluidos los anidados."""
    lineas = contenido.splitlines(keepends=True)
    salida = []
    profundidad: Optional[int] = None

    for linea in lineas:
        if profundidad is None:
            salida.append(linea)
            if _INICIO_IF_FALSO.match(linea.rstrip("\n")):
                profundidad = 1
            continue

        if _INICIO_CONDICIONAL.match(linea):
            profundidad += 1
            salida.append(_blanquear(linea))
        elif _FIN_CONDICIONAL.match(linea):
            profundidad -= 1
            if profundidad == 0:
                profundidad = None
                salida.append(linea)
            else:
                salida.append(_blanquear(linea))
        elif profundidad == 1 and _RAMA_ALTERNATIVA.match(linea):
            # `#else`/`#elif` del `#if 0`: a partir de acá el código sí compila.
            profundidad = None
            salida.append(linea)
        else:
            salida.append(_blanquear(linea))

    return "".join(salida)
