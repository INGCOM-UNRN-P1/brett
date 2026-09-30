"""Un archivo o carpeta que no existe es un error de uso, no un análisis limpio (N-ECO-18).

`brett audit no_existe.c` terminaba con 0 (sin nada que analizar): un nombre mal escrito
parecía un código sin problemas.
"""

import pytest
from typer.testing import CliRunner

from brett.cli import app

runner = CliRunner()


@pytest.mark.parametrize("comando", ["audit", "report", "optimize"])
def test_una_ruta_que_no_existe_es_un_error_de_uso(comando, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = runner.invoke(app, [comando, "no_existe.c"], env={"COLUMNS": "200"})
    assert res.exit_code == 2, res.output
    assert "no_existe.c" in res.output
