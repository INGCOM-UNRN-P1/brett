"""Ola 18: tamaños de los tipos por ABI, campos de una misma declaración y `brett optimize` como diff."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from brett.cli import app
from brett.core.layout import ABIS, AbiDesconocida, tamanio_alineacion, tipo_canonico
from brett.core.padding import analizar_archivo_c, auditar_rutas
from brett.core.reordenar import diff, reordenar

runner = CliRunner()

ALUMNO = """#include <stdio.h>

/* Un alumno del curso */
typedef struct
{
    char inicial;       // primera letra
    double promedio;
    // la cantidad de materias aprobadas
    int aprobadas;
    char activo, regular;
    long legajo;
} alumno_t;

typedef struct { char c; int x; char d; } punto_t;

typedef struct
{
    double a;
    int b;
} ya_optimo_t;
"""


@pytest.mark.parametrize("tipo, canonico", [
    ("unsigned long int", "long"), ("const char *", "pointer"), ("_Bool", "bool"), ("enum dia", "int"),
    ("long long", "long long"), ("long double", "long double"), ("unsigned", "int"), ("uint64_t", "uint64_t"),
])
def test_tipo_canonico(tipo, canonico):
    assert tipo_canonico(tipo) == canonico


def test_las_abis_difieren_donde_importa():
    assert {abi: tamanio_alineacion("long", abi) for abi in ABIS} == {
        "x86_64": (8, 8), "aarch64": (8, 8), "riscv64": (8, 8), "x86_64-windows": (4, 4), "i386": (4, 4)}
    assert tamanio_alineacion("double", "i386") == (8, 4)
    assert tamanio_alineacion("char *", "i386") == (4, 4)
    with pytest.raises(AbiDesconocida):
        tamanio_alineacion("int", "pdp11")


def test_el_mismo_struct_en_dos_abis(tmp_path):
    fuente = tmp_path / "r.h"
    fuente.write_text("typedef struct { char c; long l; double d; } registro_t;\n", encoding="utf-8")
    assert analizar_archivo_c(fuente)[0].tamanio_total_bytes == 24
    assert analizar_archivo_c(fuente, "x86_64-windows")[0].tamanio_total_bytes == 16  # long de 4
    assert analizar_archivo_c(fuente, "i386")[0].tamanio_total_bytes == 16  # double alineado a 4
    assert auditar_rutas([fuente], "i386").to_dict()["abi"] == "i386"
    res = runner.invoke(app, ["audit", str(fuente), "--abi", "pdp11"])
    assert res.exit_code == 2


def test_todos_los_campos_de_una_declaracion(tmp_path):
    fuente = tmp_path / "a.c"
    fuente.write_text(ALUMNO, encoding="utf-8")
    alumno = next(s for s in analizar_archivo_c(fuente) if s.nombre == "alumno_t")
    assert [c.nombre for c in alumno.campos] == ["inicial", "promedio", "aprobadas", "activo", "regular", "legajo"]
    assert (alumno.tamanio_total_bytes, alumno.tamanio_optimizado_bytes) == (32, 24)


def test_reordenar_conserva_declaraciones_y_comentarios(tmp_path):
    nuevo, cambiados = reordenar(ALUMNO)
    assert [s.nombre for s in cambiados] == ["alumno_t", "punto_t"]
    assert """{
    double promedio;
    long legajo;
    // la cantidad de materias aprobadas
    int aprobadas;
    char inicial; // primera letra
    char activo;
    char regular;
} alumno_t;""" in nuevo
    assert "typedef struct { int x; char c; char d; } punto_t;" in nuevo
    assert "double a;\n    int b;" in nuevo  # el que ya es óptimo no cambia
    # Y lo reordenado ocupa lo que brett promete.
    (tmp_path / "n.c").write_text(nuevo, encoding="utf-8")
    assert {s.nombre: s.tamanio_total_bytes for s in analizar_archivo_c(tmp_path / "n.c")}["alumno_t"] == 24


def test_el_diff_se_aplica_con_patch(tmp_path, monkeypatch):
    if subprocess.run(["which", "patch"], capture_output=True).returncode != 0:
        pytest.skip("hace falta patch")
    fuente = tmp_path / "alumno.c"
    fuente.write_text(ALUMNO, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, ["optimize", "alumno.c"])
    assert res.exit_code == 0 and res.stdout.startswith("--- a/alumno.c\n+++ b/alumno.c\n")
    subprocess.run(["patch", "-p1"], input=res.stdout, text=True, check=True, cwd=tmp_path, capture_output=True)
    assert fuente.read_text(encoding="utf-8") == reordenar(ALUMNO)[0]


def test_aplicar_reescribe_el_archivo(tmp_path):
    fuente = tmp_path / "alumno.c"
    fuente.write_text(ALUMNO, encoding="utf-8")
    assert runner.invoke(app, ["optimize", str(fuente), "--aplicar"]).exit_code == 0
    assert fuente.read_text(encoding="utf-8") == reordenar(ALUMNO)[0]
    assert diff(fuente)[1] == []  # ya no queda nada que ahorrar
