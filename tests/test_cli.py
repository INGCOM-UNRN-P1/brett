"""Tests de integración de la CLI de BRETT."""

import json
from pathlib import Path
from typer.testing import CliRunner
from brett.cli import app

runner = CliRunner()


def test_cli_version():
    res = runner.invoke(app, ["--version"])
    assert res.exit_code == 0
    assert "BRETT" in res.stdout


def test_cli_audit_json(tmp_path):
    fuente = tmp_path / "struct.h"
    fuente.write_text("""
    typedef struct {
        char x;
        long y;
    } t_dato;
    """)

    res = runner.invoke(app, ["audit", str(fuente), "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["total_structs"] == 1
    assert data["structs"][0]["nombre"] == "t_dato"


def test_cli_optimize(tmp_path):
    fuente = tmp_path / "struct.h"
    fuente.write_text("""
    typedef struct {
        char x;
        long y;
    } t_dato;
    """)

    res = runner.invoke(app, ["optimize", str(fuente)])
    assert res.exit_code == 0
    assert "Layout Sugerido" in res.stdout


def test_cli_doctor():
    res = runner.invoke(app, ["doctor"])
    assert res.exit_code == 0
    assert "doctor" in res.stdout.lower()

    res_json = runner.invoke(app, ["doctor", "--json"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.stdout)
    assert data["herramienta"] == "brett"
    assert data["ok"] is True


def test_help_de_optimize_describe_el_orden_real():
    """BRETT-D0403: el código ordena de mayor a menor alineación."""
    res = runner.invoke(app, ["optimize", "--help"])
    assert "mayor a menor" in res.stdout
    assert "menor a mayor" not in res.stdout
