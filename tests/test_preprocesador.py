"""Regresión de BRETT-D0304: `#if 0` no es código activo.

Tree-Sitter no ejecuta el preprocesador, así que parsea el contenido de un
`#if 0` como si estuviera vivo. Sin enmascararlo, un struct desactivado se auditaba y el
estudiante recibía un hallazgo sobre código que no se compila.
"""

from brett.core.preprocesador import enmascarar_bloques_inactivos


def test_el_cuerpo_del_if_0_se_blanquea():
    fuente = "#if 0\nstruct Muerto { char c; };\n#endif\nint vivo = 1;\n"
    enmascarado = enmascarar_bloques_inactivos(fuente)
    assert "Muerto" not in enmascarado
    assert "int vivo = 1;" in enmascarado


def test_se_preservan_offsets_y_lineas():
    """Los números de línea reportados deben seguir siendo los del original."""
    fuente = "#if 0\nstruct Muerto { char c; };\n#endif\nint vivo = 1;\n"
    enmascarado = enmascarar_bloques_inactivos(fuente)
    assert len(enmascarado) == len(fuente)
    assert enmascarado.count("\n") == fuente.count("\n")


def test_la_rama_else_sigue_viva():
    fuente = "#if 0\nstruct Muerto { char c; };\n#else\nint activo = 2;\n#endif\n"
    enmascarado = enmascarar_bloques_inactivos(fuente)
    assert "Muerto" not in enmascarado
    assert "int activo = 2;" in enmascarado


def test_condicionales_anidados_no_cierran_de_mas():
    fuente = (
        "#if 0\n#ifdef OTRA\nstruct Muerto { char c; };\n#endif\nint interno = 3;\n#endif\n"
        "int despues = 4;\n"
    )
    enmascarado = enmascarar_bloques_inactivos(fuente)
    assert "Muerto" not in enmascarado
    assert "int interno = 3;" not in enmascarado
    assert "int despues = 4;" in enmascarado


def test_un_if_normal_no_se_toca():
    fuente = "#ifdef DEBUG\nstruct Muerto { char c; };\n#endif\n"
    assert enmascarar_bloques_inactivos(fuente) == fuente
