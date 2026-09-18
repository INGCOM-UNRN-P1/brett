"""Regresión de BRETT-D0302/D0303: tipos por token exacto y structs anidados.

`long double` matcheaba por substring con `long` (8 B en vez de 16 B x86_64),
y un campo que era a su vez un struct con cuerpo propio caía al fallback
genérico de 4 B en vez de calcular su tamaño real.
"""

from pathlib import Path

import pytest

from brett.core.padding import _obtener_tamanio_alineacion, analizar_archivo_c


@pytest.mark.parametrize(
    "tipo, tamanio_esperado",
    [
        ("long double", (16, 16)),
        ("long", (8, 8)),
        ("double", (8, 8)),
        ("unsigned long", (8, 8)),
        ("unsigned int", (4, 4)),
    ],
)
def test_tipos_multipalabra_no_matchean_por_substring(tipo, tamanio_esperado):
    assert _obtener_tamanio_alineacion(tipo) == tamanio_esperado


def test_struct_con_long_double_reporta_16_bytes(tmp_path):
    archivo = tmp_path / "ld.h"
    archivo.write_text("typedef struct { char c; long double ld; } S;", encoding="utf-8")
    structs = {s.nombre: s for s in analizar_archivo_c(archivo)}
    campo_ld = next(c for c in structs["S"].campos if c.nombre == "ld")
    assert campo_ld.tamanio == 16
    assert campo_ld.alineacion == 16


def test_struct_anidado_como_campo_calcula_su_tamanio_real(tmp_path):
    """Verificado contra `sizeof` de GCC en x86_64: 24 B, no 4+8+8=20 ni el
    fallback de 4 B que rompía todos los offsets siguientes."""
    archivo = tmp_path / "anidado.h"
    archivo.write_text(
        "typedef struct { char c; struct { int p; int q; } inner; double d; } S;",
        encoding="utf-8",
    )
    structs = {s.nombre: s for s in analizar_archivo_c(archivo)}
    assert structs["S"].tamanio_total_bytes == 24
    campo_inner = next(c for c in structs["S"].campos if c.nombre == "inner")
    assert campo_inner.tamanio == 8
    assert campo_inner.alineacion == 4
