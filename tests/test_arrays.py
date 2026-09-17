"""Regresión de BRETT-D0301: los arreglos deben contarse por su tamaño real.

Los tamaños esperados de cada caso están verificados contra `sizeof` de GCC
en x86_64; si alguno cambia, el motor volvió a contar un arreglo como un
único elemento (o rompió la semántica del código reordenado).
"""

from pathlib import Path

import pytest

from brett.core.padding import analizar_archivo_c


def _analizar(tmp_path: Path, fuente: str):
    archivo = tmp_path / "structs.h"
    archivo.write_text(fuente, encoding="utf-8")
    return {s.nombre: s for s in analizar_archivo_c(archivo)}


@pytest.mark.parametrize(
    "nombre, cuerpo, tamanio_gcc",
    [
        ("ConArray", "char c; int arr[10]; double d;", 56),
        ("ConMatriz", "int matriz[3][4]; char flag;", 52),
        ("ConPunteros", "char *punteros[4]; char c;", 40),
        ("PunteroAArreglo", "char (*pa)[4]; char c;", 16),
        ("Alumno", "int id; char nombre[32]; float nota;", 40),
        ("Simple", "char c; int i;", 8),
    ],
)
def test_tamanio_coincide_con_gcc(tmp_path, nombre, cuerpo, tamanio_gcc):
    structs = _analizar(tmp_path, f"typedef struct {{ {cuerpo} }} {nombre};")
    assert structs[nombre].tamanio_total_bytes == tamanio_gcc


def test_campo_arreglo_reporta_bytes_del_arreglo_completo(tmp_path):
    structs = _analizar(tmp_path, "typedef struct { int arr[10]; } S;")
    campo = structs["S"].campos[0]
    assert campo.tamanio == 40
    assert campo.alineacion == 4  # la alineación es la del elemento, no la del total


def test_codigo_optimizado_preserva_la_dimension(tmp_path):
    """El reorden sugerido no puede cambiar la semántica: `int arr[10]` debe
    seguir siendo un arreglo en el código emitido."""
    structs = _analizar(tmp_path, "typedef struct { char c; int arr[10]; double d; } S;")
    codigo = structs["S"].codigo_optimizado
    assert "int arr[10];" in codigo
    assert "int arr;" not in codigo


def test_matriz_preserva_todas_las_dimensiones_en_orden(tmp_path):
    structs = _analizar(tmp_path, "typedef struct { int m[3][4]; } S;")
    assert "int m[3][4];" in structs["S"].codigo_optimizado
    assert structs["S"].campos[0].tamanio == 48


def test_dimension_simbolica_se_marca_en_vez_de_asumir_uno(tmp_path):
    """`int v[MAX]` no se puede resolver sin preprocesador: se marca explícito."""
    structs = _analizar(tmp_path, "typedef struct { char nombre[MAX]; int id; } S;")
    assert structs["S"].tiene_dimensiones_no_resueltas is True
    assert structs["S"].campos[0].dimension_no_resuelta is True


def test_miembro_flexible_no_aporta_bytes(tmp_path):
    """`int flex[]` al final de un struct no suma al sizeof (C11 §6.7.2.1)."""
    structs = _analizar(tmp_path, "typedef struct { int n; int flex[]; } S;")
    assert structs["S"].tamanio_total_bytes == 4
