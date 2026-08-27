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
