"""Tests unitarios para el cálculo de padding en BRETT."""

from pathlib import Path
import pytest
from brett.core.padding import analizar_archivo_c, auditar_rutas


def test_detectar_padding_en_struct_desalineado(tmp_path):
    fuente = tmp_path / "struct.h"
    fuente.write_text("""
    typedef struct {
        char a;     // 1 byte + 7 bytes padding
        double b;   // 8 bytes
        char c;     // 1 byte + 7 bytes padding
    } t_nodo;
    """)

    structs = analizar_archivo_c(fuente)
    assert len(structs) == 1
    s = structs[0]
    assert s.nombre == "t_nodo"
    assert s.tamanio_total_bytes == 24
    assert s.tamanio_datos_utiles_bytes == 10
    assert s.bytes_padding_desperdiciados == 14
    assert s.tamanio_optimizado_bytes == 16
    assert s.bytes_ahorrados == 8


def test_struct_ya_optimizado(tmp_path):
    fuente = tmp_path / "struct_opt.h"
    fuente.write_text("""
    typedef struct {
        double b;   // 8 bytes
        char a;     // 1 byte
        char c;     // 1 byte + 6 bytes padding al final
    } t_optimizado;
    """)

    structs = analizar_archivo_c(fuente)
    assert len(structs) == 1
    s = structs[0]
    assert s.tamanio_total_bytes == 16
    assert s.bytes_ahorrados == 0


def test_brett_d0201_corpus_real_sin_segfault():
    """Verifica que auditar archivos complejos del corpus no arroje SIGSEGV (BRETT-D0201)."""
    corpus_file = Path(__file__).resolve().parents[2] / "librerias" / "lib_test" / "include" / "p1_test.h"
    if corpus_file.is_file():
        structs = analizar_archivo_c(corpus_file)
        assert isinstance(structs, list)
        assert len(structs) > 0

