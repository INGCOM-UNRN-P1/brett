"""Tests adicionales para maximizar la cobertura en BRETT."""

import json
from pathlib import Path
from typer.testing import CliRunner
import brett.cli
from brett.cli import app
from brett.core.padding import auditar_rutas, analizar_archivo_c
from brett.ripley_plugin import BrettPlugin

runner = CliRunner()


def test_plugin_execution(tmp_path):
    p = BrettPlugin()
    assert p.is_available() is True

    fuente = tmp_path / "tipos.h"
    fuente.write_text("""
    typedef struct {
        char a;
        double b;
        char c;
    } t_nodo;
    """)

    res = p.execute(tmp_path, {})
    assert res["total_structs"] == 1
    assert res["total_bytes_ahorrables"] > 0
    assert len(res["observaciones"]) == 1


def test_cli_audit_rich_and_empty(tmp_path):
    fuente = tmp_path / "tipos.h"
    fuente.write_text("""
    typedef struct {
        char a;
        int b;
    } t_item;
    """)

    # Rich table
    res = runner.invoke(app, ["audit", str(fuente)])
    assert res.exit_code == 0
    assert "Auditoría de Padding" in res.stdout

    # No structs
    empty_f = tmp_path / "empty.c"
    empty_f.write_text("int x = 1;\n")
    res_empty = runner.invoke(app, ["audit", str(empty_f)])
    assert res_empty.exit_code == 0
    assert "No se encontraron" in res_empty.stdout


def test_cli_optimize_empty(tmp_path):
    empty_f = tmp_path / "empty.c"
    empty_f.write_text("int x = 1;\n")
    res = runner.invoke(app, ["optimize", str(empty_f)])
    assert res.exit_code == 0
    assert "No se encontraron" in res.stdout


def test_padding_directory_and_arrays(tmp_path):
    sub = tmp_path / "include"
    sub.mkdir()
    (sub / "nodo.h").write_text("""
    typedef struct {
        char nombre[32];
        int edad;
    } t_persona;
    """)
    (sub / "other.txt").write_text("ignorar\n")

    rep = auditar_rutas([sub])
    assert len(rep.structs) == 1
    assert rep.structs[0].nombre == "t_persona"


def test_cli_main_block(monkeypatch):
    monkeypatch.setattr("sys.argv", ["brett", "--version"])
    try:
        brett.cli.main()
    except SystemExit as e:
        assert e.code == 0
