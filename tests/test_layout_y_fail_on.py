"""Motor de layout compartido con kane y `--fail-on N`."""

from pathlib import Path

from typer.testing import CliRunner

from brett.cli import app
from brett.core.layout import Elemento, disponer

runner = CliRunner()


def test_disponer_con_relleno_intermedio_y_final():
    elementos, total = disponer([("c", 1, 1), ("i", 4, 4), ("d", 1, 1)])
    assert total == 12
    assert elementos == [Elemento("c", 0, 1), Elemento("_pad_1", 1, 3, True), Elemento("i", 4, 4),
                         Elemento("d", 8, 1), Elemento("_tail_pad_9", 9, 3, True)]


def test_disponer_vacio():
    assert disponer([]) == ([], 1)


def _struct(tmp_path: Path) -> Path:
    f = tmp_path / "s.h"
    f.write_text("typedef struct {\n    char a;\n    double b;\n    char c;\n} S;\n", encoding="utf-8")
    return f  # 24 B; reordenado 16 B: ahorro de 8 B


def test_fail_on(tmp_path):
    f = _struct(tmp_path)
    assert runner.invoke(app, ["audit", str(f), "--json"]).exit_code == 1
    assert runner.invoke(app, ["audit", str(f), "--json", "--fail-on", "16"]).exit_code == 0
    assert runner.invoke(app, ["audit", str(f), "--json", "--fail-on", "8"]).exit_code == 1
