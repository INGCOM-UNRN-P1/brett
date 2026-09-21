"""Regresión de BRETT-D0901: el JSON de la CLI debe cumplir el contrato de satélite.

Ripley consume brett por la vía CLI (`brett audit --json`) y normaliza cada
struct con `normalize_finding`, que tiene una rama específica para brett
activada por la clave `wasted_padding_bytes`. Sin esas claves el hallazgo se
degradaba a `codigo="padding"` con mensaje vacío, y el proyecto se daba por
aprobado pese a tener bytes desperdiciados.
"""

from pathlib import Path

import pytest

from brett.core.padding import auditar_rutas

FUENTE = """
typedef struct { char a; double b; char c; } Malo;
typedef struct { double b; char a; char c; } Bueno;
"""


def _reporte(tmp_path: Path):
    archivo = tmp_path / "structs.h"
    archivo.write_text(FUENTE, encoding="utf-8")
    return auditar_rutas([tmp_path]).to_dict()


def test_veredicto_expuesto_en_el_json(tmp_path):
    """`ok`/`passed` deben reflejar el ahorro real, no asumirse True."""
    data = _reporte(tmp_path)
    assert data["ok"] is False
    assert data["passed"] is False
    assert data["total_bytes_ahorrables"] > 0


def test_proyecto_optimo_aprueba(tmp_path):
    archivo = tmp_path / "ok.h"
    archivo.write_text("typedef struct { double b; char a; char c; } Bueno;", encoding="utf-8")
    data = auditar_rutas([tmp_path]).to_dict()
    assert data["ok"] is True
    assert data["passed"] is True


def test_cada_struct_expone_las_claves_del_contrato(tmp_path):
    data = _reporte(tmp_path)
    requeridas = {"name", "wasted_padding_bytes", "message", "suggestion", "file_path", "line_number"}
    for struct in data["structs"]:
        assert requeridas <= set(struct), f"faltan claves del contrato: {requeridas - set(struct)}"
        assert struct["message"].strip(), "el mensaje no puede llegar vacío a ripley"


def test_severidad_depende_del_ahorro_reordenable(tmp_path):
    """El padding inevitable por alineación no debe reportarse como defecto."""
    data = _reporte(tmp_path)
    por_nombre = {s["name"]: s for s in data["structs"]}
    assert por_nombre["Malo"]["wasted_padding_bytes"] > 0
    assert por_nombre["Malo"]["suggestion"].strip()
    # `Bueno` desperdicia padding inevitable, pero nada reordenable:
    assert por_nombre["Bueno"]["wasted_padding_bytes"] == 0
    assert por_nombre["Bueno"]["suggestion"] == ""


def test_normalize_finding_de_ripley_produce_un_hallazgo_util(tmp_path):
    """Contrato end-to-end contra el normalizador real de ripley.

    Se saltea si ripley no está instalado: brett es un satélite y no debe
    depender del orquestador, pero cuando ambos conviven el contrato se
    verifica de punta a punta.
    """
    pytest.importorskip("ripley", reason="ripley no instalado; contrato verificado solo por claves")
    from ripley.core.entrypoints import normalize_finding

    data = _reporte(tmp_path)
    por_nombre = {s["name"]: s for s in data["structs"]}

    malo = normalize_finding(por_nombre["Malo"], "padding")
    assert malo["codigo"] == "PADDING_INEFFICIENT"
    assert malo["severidad"] == "ADVERTENCIA"
    assert malo["mensaje"].strip()

    bueno = normalize_finding(por_nombre["Bueno"], "padding")
    assert bueno["codigo"] == "PADDING_OPTIMAL"
    assert bueno["severidad"] == "INFO"


def test_nombre_del_plugin_coincide_con_el_entry_point():
    """BRETT-D0902: name debe ser el del entry-point/catálogo (`padding`)."""
    from importlib.metadata import entry_points

    from brett.ripley_plugin import BrettPlugin

    nombres = {ep.name for ep in entry_points(group="ripley.plugins") if ep.value.startswith("brett.")}
    assert BrettPlugin.name in nombres
