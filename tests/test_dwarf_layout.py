"""El layout medido por el compilador (ola R2). El oráculo es `sizeof`/`offsetof` del propio gcc."""

import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from brett.cli import app
from brett.core import dwarf_layout
from brett.core.dwarf_layout import capturar_layouts, parsear_pahole
from brett.core.padding import analizar_archivo_c, auditar_rutas
from brett.core.reordenar import diff

hay_gcc = shutil.which("gcc") is not None
con_gcc_y_gdb = pytest.mark.skipif(not hay_gcc or shutil.which("gdb") is None, reason="hace falta gcc y gdb")
con_pahole = pytest.mark.skipif(not hay_gcc or shutil.which("pahole") is None, reason="hace falta gcc y pahole")

TIPOS = """\
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#define MAX 32
typedef int mi_entero;
typedef struct { char c; double d; } Interno;
union numero { int i; double d; };
enum color { ROJO, VERDE };
typedef struct persona {
    char nombre[MAX];
    bool activo;
    mi_entero edad;
    Interno interno;
    union numero n;
    enum color color;
    long double ld;
    FILE *archivo;
    int matriz[3][MAX / 8];
    char a, b;
    void (*avisar)(int);
    uint16_t corto;
} Persona;
struct sin_typedef { char a; long b; char c; };
struct __attribute__((packed)) empaquetado { char a; int b; };
struct bits { unsigned a : 3; unsigned b : 5; char c; int d; };
struct flexible { char c; int v[]; };
"""


def _escribir(tmp_path: Path, texto: str, nombre: str = "tipos.c") -> Path:
    archivo = tmp_path / nombre
    archivo.write_text(texto, encoding="utf-8")
    return archivo


def _gcc_dice(tmp_path: Path, codigo: str, expresiones) -> list:
    """Los valores de `expresiones` en un programa compilado con gcc."""
    impresiones = "".join(f'printf("%zu\\n", (size_t)({e}));\n' for e in expresiones)
    fuente = _escribir(tmp_path, f"{codigo}\nint main(void) {{\n{impresiones}return 0;\n}}\n", "oraculo.c")
    binario = tmp_path / "oraculo"
    subprocess.run(["gcc", "-w", "-std=gnu11", str(fuente), "-o", str(binario)], check=True)
    return [int(x) for x in subprocess.run([str(binario)], capture_output=True, text=True, check=True).stdout.split()]


@pytest.fixture
def structs(tmp_path):
    return {s.nombre: s for s in analizar_archivo_c(_escribir(tmp_path, TIPOS))}


@con_gcc_y_gdb
def test_todos_los_structs_se_miden(structs):
    assert {s.origen for s in structs.values()} == {"dwarf"}
    assert {"Interno", "Persona", "sin_typedef", "empaquetado", "bits", "flexible"} == set(structs)


@con_gcc_y_gdb
@pytest.mark.parametrize("nombre, tipo_c", [
    ("Interno", "Interno"), ("Persona", "Persona"), ("sin_typedef", "struct sin_typedef"),
    ("empaquetado", "struct empaquetado"), ("bits", "struct bits"), ("flexible", "struct flexible"),
])
def test_el_tamanio_coincide_con_sizeof(tmp_path, structs, nombre, tipo_c):
    assert [structs[nombre].tamanio_total_bytes] == _gcc_dice(tmp_path, TIPOS, [f"sizeof({tipo_c})"])


@con_gcc_y_gdb
def test_offsets_y_alineaciones_coinciden_con_gcc(tmp_path, structs):
    campos = structs["Persona"].campos
    offsets = _gcc_dice(tmp_path, TIPOS, [f"offsetof(Persona, {c.nombre})" for c in campos])
    alineaciones = _gcc_dice(tmp_path, TIPOS, [f"_Alignof(((Persona *)0)->{c.nombre})" for c in campos])

    assert [c.offset_original for c in campos] == offsets
    assert [c.alineacion for c in campos] == alineaciones


@con_gcc_y_gdb
def test_la_dimension_simbolica_se_resuelve_y_conserva_su_texto(structs):
    nombre = structs["Persona"].campos[0]

    assert nombre.tamanio == 32
    assert nombre.sufijo_array == "[MAX]"
    assert not structs["Persona"].tiene_dimensiones_no_resueltas


@con_gcc_y_gdb
def test_no_se_sugiere_reordenar_lo_que_el_modelo_natural_no_explica(structs):
    assert structs["empaquetado"].bytes_ahorrados == 0
    assert structs["bits"].bytes_ahorrados == 0
    assert structs["bits"].tamanio_optimizado_bytes == structs["bits"].tamanio_total_bytes


@con_gcc_y_gdb
def test_pragma_pack_no_inventa_ahorro(tmp_path):
    s = analizar_archivo_c(_escribir(tmp_path, "#pragma pack(push, 1)\ntypedef struct { char a; int b; short c; } P;\n#pragma pack(pop)\n"))[0]

    assert (s.tamanio_total_bytes, s.bytes_ahorrados, s.bytes_padding_desperdiciados) == (7, 0, 0)


@con_gcc_y_gdb
def test_los_bitfields_ocupan_lo_que_miden(structs):
    a, b, *_ = structs["bits"].campos

    assert (a.bits, b.bits) == (3, 5)
    assert "a : 3" in structs["bits"].codigo_optimizado
    assert structs["bits"].tamanio_datos_utiles_bytes == 1 + 1 + 4


@con_gcc_y_gdb
def test_rama_inactiva_del_preprocesador(tmp_path):
    archivo = _escribir(tmp_path, "#ifdef NO_DEFINIDA\n#define X long\n#else\n#define X char\n#endif\n"
                                  "typedef struct {\n    char a;\n#ifdef NO_DEFINIDA\n    long fantasma;\n#endif\n"
                                  "    X b;\n} S;\n")
    s = analizar_archivo_c(archivo)[0]

    assert [c.nombre for c in s.campos] == ["a", "b"]
    assert s.tamanio_total_bytes == 2


@con_gcc_y_gdb
def test_cabecera_sola(tmp_path):
    s = analizar_archivo_c(_escribir(tmp_path, "#define N 3\ntypedef struct nodo { char v[N]; struct nodo *sig; } Nodo;\n", "nodo.h"))[0]

    assert (s.origen, s.tamanio_total_bytes) == ("dwarf", 16)


@con_gcc_y_gdb
def test_typedef_de_otro_archivo(tmp_path):
    _escribir(tmp_path, "#define LARGO 10\ntypedef long entero_t;\n", "comun.h")
    s = analizar_archivo_c(_escribir(tmp_path, '#include "comun.h"\nstruct r { char c[LARGO]; entero_t e; };\n'))[0]

    assert (s.origen, s.tamanio_total_bytes, s.campos[1].alineacion) == ("dwarf", 24, 8)


@con_gcc_y_gdb
def test_funcion_sin_declarar_no_impide_medir(tmp_path):
    s = analizar_archivo_c(_escribir(tmp_path, "struct z { char a; int v[4]; };\nint main(void) { nada(); return 0; }\n"))[0]

    assert s.origen == "dwarf"


@con_gcc_y_gdb
def test_el_diff_decide_con_el_tamanio_medido(tmp_path):
    # Con la tabla, `Oculto` valdría 4 B y este struct parecería no tener nada que ahorrar.
    archivo = _escribir(tmp_path, "typedef long Oculto;\nstruct s {\n    char a;\n    Oculto b;\n    char c;\n};\n")

    _, cambiados = diff(archivo, nombre="tipos.c")

    assert cambiados[0].tamanio_total_bytes == 24
    assert cambiados[0].tamanio_optimizado_bytes == 16


@con_gcc_y_gdb
def test_no_quedan_archivos_junto_al_fuente(tmp_path):
    archivo = _escribir(tmp_path, TIPOS)

    analizar_archivo_c(archivo)

    assert [p.name for p in tmp_path.iterdir()] == ["tipos.c"]


# ── Degradación ───────────────────────────────────────────────────────────────────────────────

def test_si_no_compila_se_estima_y_se_dice_por_que(tmp_path):
    s = analizar_archivo_c(_escribir(tmp_path, "typedef struct { char c; int v[MAX]; } S;\nint main(void) { return 0 }\n"))[0]

    assert s.origen == "estimado"
    assert s.tiene_dimensiones_no_resueltas
    assert "compila" in s.motivo_estimado or "gcc" in s.motivo_estimado


@con_gcc_y_gdb
def test_struct_local_se_estima(tmp_path):
    s = analizar_archivo_c(_escribir(tmp_path, "int main(void) { struct l { char a; int b; } v; (void)v; return 0; }\n"))[0]

    assert s.origen == "estimado"
    assert s.motivo_estimado == dwarf_layout.SIN_NOMBRE_VISIBLE


def test_sin_gcc(tmp_path, monkeypatch):
    monkeypatch.setattr(dwarf_layout.shutil, "which", lambda _: None)

    s = analizar_archivo_c(_escribir(tmp_path, "struct z { char a; int b; };\n"))[0]

    assert (s.origen, s.tamanio_total_bytes) == ("estimado", 8)
    assert "gcc" in s.motivo_estimado


@pytest.mark.skipif(not hay_gcc, reason="hace falta gcc")
def test_sin_gdb_ni_pahole(tmp_path, monkeypatch):
    monkeypatch.setattr(dwarf_layout, "_layouts_gdb", lambda *a: None)
    monkeypatch.setattr(dwarf_layout, "_layouts_pahole", lambda *a: None)

    s = analizar_archivo_c(_escribir(tmp_path, "struct z { char a; int b; };\n"))[0]

    assert s.origen == "estimado"
    assert "gdb" in s.motivo_estimado


@pytest.mark.skipif(not hay_gcc, reason="hace falta gcc")
def test_una_abi_ajena_usa_la_tabla(tmp_path, monkeypatch):
    monkeypatch.setattr(dwarf_layout, "_abi_nativa", lambda cc: "x86_64")

    s = analizar_archivo_c(_escribir(tmp_path, "struct z { char a; long b; };\n"), abi="x86_64-windows")[0]

    assert (s.origen, s.tamanio_total_bytes) == ("estimado", 8)
    assert "x86_64-windows" in s.motivo_estimado


@pytest.mark.parametrize("maquina, abi", [
    ("x86_64-redhat-linux", "x86_64"), ("x86_64-w64-mingw32", "x86_64-windows"), ("aarch64-linux-gnu", "aarch64"),
    ("riscv64-linux-gnu", "riscv64"), ("i686-linux-gnu", "i386"), ("powerpc64le-linux-gnu", None),
])
def test_abi_nativa(monkeypatch, maquina, abi):
    dwarf_layout._abi_nativa.cache_clear()
    monkeypatch.setattr(dwarf_layout.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=maquina + "\n"))

    assert dwarf_layout._abi_nativa("gcc") == abi
    dwarf_layout._abi_nativa.cache_clear()


# ── pahole ────────────────────────────────────────────────────────────────────────────────────

@con_pahole
def test_pahole_da_los_mismos_tamanios_y_offsets_que_gdb(tmp_path, monkeypatch):
    archivo = _escribir(tmp_path, TIPOS)
    con_gdb = {s.nombre: s for s in analizar_archivo_c(archivo)}
    monkeypatch.setattr(dwarf_layout, "_layouts_gdb", lambda *a: None)
    con_pahole_ = {s.nombre: s for s in analizar_archivo_c(archivo)}

    for nombre, s in con_gdb.items():
        otro = con_pahole_[nombre]
        assert otro.origen == "dwarf", nombre
        assert otro.tamanio_total_bytes == s.tamanio_total_bytes, nombre
        assert [(c.nombre, c.offset_original, c.tamanio) for c in otro.campos] == \
               [(c.nombre, c.offset_original, c.tamanio) for c in s.campos], nombre


def test_pahole_alineacion_acotada():
    salida = ("struct s {\n\tchar                       c;                    /*     0     1 */\n"
              "\tInterno                    i;                    /*     8    16 */\n\n"
              "\t/* size: 24, cachelines: 1, members: 2 */\n};\n")

    c, i = parsear_pahole(salida, "x86_64")["s"].campos

    assert (c.alineacion, i.alineacion) == (1, 8)


def test_pahole_typedef_anonimo():
    salida = "typedef struct {\n\tint                        a;                    /*     0     4 */\n\n\t/* size: 4 */\n} T;\n"

    assert parsear_pahole(salida, "x86_64")["T"].tamanio == 4


# ── CLI ───────────────────────────────────────────────────────────────────────────────────────

def test_audit_avisa_si_los_tamanios_son_estimados(tmp_path):
    archivo = _escribir(tmp_path, "struct z { char a; int b; };\nint main(void) { return 0 }\n")

    res = CliRunner().invoke(app, ["audit", str(archivo)])

    assert "estimados" in res.output


def test_el_informe_de_dredd_avisa_si_son_estimados(tmp_path):
    from brett.cli import generar_seccion_markdown

    reporte = auditar_rutas([_escribir(tmp_path, "struct z { char a; int b; };\nint main(void) { return 0 }\n")])

    assert "Tamaños estimados" in generar_seccion_markdown(reporte)


def test_doctor_nombra_gdb_y_pahole():
    res = CliRunner().invoke(app, ["doctor", "--json"])

    assert "GDB" in res.output and "pahole" in res.output
