"""El layout real de los structs: compilar a un objeto temporal y leer lo que dejó gcc en el DWARF.

Resuelve lo que un análisis del fuente no puede: `int v[MAX]`, typedefs de otros archivos, `union`,
bitfields y `packed`. El motor es la API Python de gdb, que entrega tamaño, offset y alineación ya
estructurados. `pahole` queda de respaldo: da tamaños y offsets, pero no la alineación, que hay que
acotar; `ptype /o` no sirve porque no informa alineación y se desactiva con miembros flexibles.

Si no se puede medir, `capturar_layouts` dice por qué y brett se queda con la estimación del fuente.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from brett.core.layout import tamanio_alineacion, tipo_canonico, ABIS

TIEMPO_LIMITE = 10  # segundos, para gcc y para gdb

# Sin -fno-eliminate-unused-debug-types, gcc no deja en el DWARF los structs que el archivo solo
# declara, que son todos los de un .h. -fpermissive: una función sin declarar no impide medir.
OPCIONES_GCC = ["-g", "-O0", "-std=gnu11", "-w", "-fpermissive", "-fno-eliminate-unused-debug-types"]

COMPILA_ES_NECESARIO = "El archivo todavía no compila: los tamaños son una estimación a partir del fuente."
SIN_NOMBRE_VISIBLE = "El compilador no lo expone con ese nombre (está dentro de una función o no tiene nombre)."


@dataclass(frozen=True)
class CampoDwarf:
    nombre: Optional[str]  # None: un struct o union anónimo
    tipo: str
    sufijo_array: str
    offset: int
    tamanio: int
    alineacion: int
    bits: int = 0  # ancho de un bitfield; 0 en cualquier otro campo


@dataclass(frozen=True)
class LayoutDwarf:
    tamanio: int
    campos: Tuple[CampoDwarf, ...]


Layouts = Dict[str, LayoutDwarf]


# ── ABI ───────────────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=None)
def _abi_nativa(cc: str) -> Optional[str]:
    """La ABI (de `layout.ABIS`) para la que compila `cc` sin opciones."""
    try:
        maquina = subprocess.run([cc, "-dumpmachine"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    if "mingw" in maquina:
        return "x86_64-windows" if maquina.startswith("x86_64") else None
    if re.match(r"i[3-6]86", maquina):
        return "i386"
    return next((abi for abi in ("x86_64", "aarch64", "riscv64") if maquina.startswith(abi)), None)


def _opciones_abi(cc: str, abi: str) -> Optional[List[str]]:
    """Las opciones para compilar para `abi`, o None si este gcc no puede."""
    nativa = _abi_nativa(cc)
    if abi == nativa:
        return []
    return ["-m32"] if abi == "i386" and nativa == "x86_64" else None


# ── gdb ───────────────────────────────────────────────────────────────────────────────────────

# Corre dentro del Python de gdb. Lee los nombres y deja el resultado en archivos: la salida de gdb
# no se interpreta.
_SCRIPT_GDB = r'''
import json
import os

import gdb


def buscar(nombre):
    for candidato in ("struct " + nombre, nombre):
        try:
            tipo = gdb.lookup_type(candidato).strip_typedefs()
        except gdb.error:
            continue
        if tipo.code == gdb.TYPE_CODE_STRUCT:
            return tipo
    return None


def base_y_sufijo(tipo):
    sufijo = ""
    while tipo.code == gdb.TYPE_CODE_ARRAY:
        try:
            inferior, superior = tipo.range()
            cantidad = superior - inferior + 1
        except gdb.error:
            cantidad = 0
        sufijo += "[%d]" % cantidad if cantidad > 0 else "[]"
        tipo = tipo.target()
    return str(tipo), sufijo


def campo(f):
    tipo, sufijo = base_y_sufijo(f.type)
    return {"nombre": f.name, "tipo": tipo, "sufijo_array": sufijo, "offset": f.bitpos // 8,
            "tamanio": f.type.sizeof, "alineacion": f.type.alignof, "bits": f.bitsize}


with open(os.environ["BRETT_NOMBRES"], encoding="utf-8") as entrada:
    nombres = json.load(entrada)
resultado = {}
for nombre in nombres:
    tipo = buscar(nombre)
    if tipo is not None:
        resultado[nombre] = {"tamanio": tipo.sizeof, "campos": [campo(f) for f in tipo.fields()]}
with open(os.environ["BRETT_LAYOUTS"], "w", encoding="utf-8") as salida:
    json.dump(resultado, salida)
'''


def _layouts_gdb(objeto: Path, nombres: Sequence[str], carpeta: Path) -> Optional[Layouts]:
    """Los layouts que da gdb, o None si no está o no trae Python."""
    gdb = shutil.which("gdb")
    if gdb is None:
        return None
    script, entrada, salida = carpeta / "layout.py", carpeta / "nombres.json", carpeta / "layouts.json"
    script.write_text(_SCRIPT_GDB, encoding="utf-8")
    entrada.write_text(json.dumps(list(nombres)), encoding="utf-8")
    entorno = {**os.environ, "BRETT_NOMBRES": str(entrada), "BRETT_LAYOUTS": str(salida)}
    # El objeto sale del código del alumno: nada de cargar los scripts que pudiera traer.
    cmd = [gdb, "-batch", "-nx", "-iex", "set auto-load off", "-iex", "set debuginfod enabled off",
           "-x", str(script), str(objeto)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=TIEMPO_LIMITE, env=entorno)
        datos = json.loads(salida.read_text(encoding="utf-8"))
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return {nombre: LayoutDwarf(d["tamanio"], tuple(CampoDwarf(**c) for c in d["campos"]))
            for nombre, d in datos.items()}


# ── pahole ────────────────────────────────────────────────────────────────────────────────────

_PAHOLE_APERTURA = re.compile(r"^(?:typedef )?struct(?: (?P<etiqueta>\w+))? \{$")
_PAHOLE_CIERRE = re.compile(r"^\}(?: __attribute__\(\(.*\)\))?(?: (?P<alias>\w+))?;")
_PAHOLE_CAMPO = re.compile(r"^\t(?P<decl>[^\s/}].*?;)\s*/\*\s*(?P<offset>\d+)(?::\s*(?P<bit>\d+))?\s+(?P<tamanio>\d+)\s*\*/$")
_PAHOLE_ANONIMO = re.compile(r"^\t\}(?P<resto>.*?;)\s*/\*\s*(?P<offset>\d+)\s+(?P<tamanio>\d+)\s*\*/$")
_PAHOLE_TOTAL = re.compile(r"/\* size: (?P<tamanio>\d+)")
_PAHOLE_ALIAS = re.compile(r"^typedef struct (?P<etiqueta>\w+) (?P<alias>\w+);$", re.MULTILINE)
_DECLARADOR = re.compile(r"(?:\(\*\s*(?P<funcion>\w+)\)\(.*\)(?:\[\d*\])*|(?P<nombre>\w+)(?P<sufijo>(?:\[\d*\])*)(?::(?P<bits>\d+))?);$")


def _potencia_de_dos(valor: int) -> int:
    """La mayor potencia de dos que divide a `valor`."""
    return valor & -valor if valor else 1 << 12


def _alineacion_pahole(tipo: str, offset: int, tamanio: int, abi: str) -> int:
    """pahole no informa la alineación. La de un tipo primitivo sale de la tabla; la de un typedef o
    un struct se acota: siempre divide al offset y al tamaño."""
    if tipo_canonico(tipo) in ABIS[abi]:
        return tamanio_alineacion(tipo, abi)[1]
    return max(1, min(_potencia_de_dos(offset), _potencia_de_dos(tamanio), 16))


def _campo_pahole(declaracion: str, offset: int, tamanio: int, abi: str) -> Optional[CampoDwarf]:
    m = _DECLARADOR.search(declaracion)
    if m is None:
        return None
    nombre = m.group("funcion") or m.group("nombre")
    tipo = declaracion[:m.start()].strip()
    bits = int(m.group("bits") or 0)
    return CampoDwarf(nombre, tipo, m.group("sufijo") or "", offset, tamanio,
                      _alineacion_pahole(tipo, offset, tamanio, abi), bits)


def parsear_pahole(salida: str, abi: str) -> Layouts:
    """Los structs del texto de pahole, por etiqueta y por alias de typedef."""
    layouts: Layouts = {}
    etiqueta: Optional[str] = None
    campos: List[CampoDwarf] = []
    total = 0
    adentro = False
    for linea in salida.splitlines():
        if not adentro:
            apertura = _PAHOLE_APERTURA.match(linea)
            if apertura:
                adentro, etiqueta, campos, total = True, apertura.group("etiqueta"), [], 0
            continue
        cierre = _PAHOLE_CIERRE.match(linea)
        if cierre:
            for nombre in (etiqueta, cierre.group("alias")):
                if nombre:
                    layouts[nombre] = LayoutDwarf(total, tuple(campos))
            adentro = False
            continue
        medida = _PAHOLE_TOTAL.search(linea)
        if medida:
            total = int(medida.group("tamanio"))
            continue
        simple, anonimo = _PAHOLE_CAMPO.match(linea), _PAHOLE_ANONIMO.match(linea)
        if simple:
            # Un bitfield viene como «unidad:bit»; se ubica en el byte donde empieza, como en gdb.
            offset = int(simple.group("offset")) + int(simple.group("bit") or 0) // 8
            campo = _campo_pahole(simple.group("decl"), offset, int(simple.group("tamanio")), abi)
            if campo:
                campos.append(campo)
        elif anonimo:
            offset, tamanio = int(anonimo.group("offset")), int(anonimo.group("tamanio"))
            nombre_interno = anonimo.group("resto").strip(" ;") or None
            campos.append(CampoDwarf(nombre_interno, "struct", "", offset, tamanio,
                                     _alineacion_pahole("struct", offset, tamanio, abi)))
    return layouts


def _correr_pahole(pahole: str, objeto: Path, nombres: Sequence[str]) -> Optional[str]:
    try:
        res = subprocess.run([pahole, "-C", ",".join(nombres), str(objeto)], capture_output=True, text=True,
                             errors="replace", timeout=TIEMPO_LIMITE)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


def _layouts_pahole(objeto: Path, nombres: Sequence[str], abi: str) -> Optional[Layouts]:
    """Los layouts que da pahole, o None si no está. Se le piden por nombre porque si no omite los
    typedefs de structs anónimos; a `typedef struct t {…} A` responde sin cuerpo, y hay que pedir `t`."""
    pahole = shutil.which("pahole")
    salida = _correr_pahole(pahole, objeto, nombres) if pahole else None
    if pahole is None or salida is None:
        return None
    layouts = parsear_pahole(salida, abi)
    alias = {m.group("alias"): m.group("etiqueta") for m in _PAHOLE_ALIAS.finditer(salida)}
    if alias:
        de_las_etiquetas = parsear_pahole(_correr_pahole(pahole, objeto, list(alias.values())) or "", abi)
        layouts.update({a: de_las_etiquetas[e] for a, e in alias.items() if e in de_las_etiquetas})
    return {n: layouts[n] for n in nombres if n in layouts}


# ── Captura ───────────────────────────────────────────────────────────────────────────────────

def capturar_layouts(archivo: Path, nombres: Sequence[str], abi: str) -> Tuple[Layouts, str]:
    """Los layouts medidos de los structs `nombres` de `archivo`; si no hay, el motivo para el alumno.

    Todo pasa en una carpeta temporal: al lado del fuente no queda nada.
    """
    cc = shutil.which("gcc")
    if cc is None:
        return {}, "Falta gcc: instalalo para que brett mida los tamaños reales (ver `brett doctor`)."
    opciones_abi = _opciones_abi(cc, abi)
    if opciones_abi is None:
        return {}, f"El gcc de este sistema no compila para {abi}: los tamaños salen de la tabla de esa ABI."
    archivo = Path(archivo).resolve()
    with tempfile.TemporaryDirectory(prefix="brett_") as temporal:
        carpeta = Path(temporal)
        objeto = carpeta / "layout.o"
        # -x c: un .h se compilaría como cabecera precompilada, sin DWARF.
        cmd = [cc, *OPCIONES_GCC, *opciones_abi, "-I", str(archivo.parent), "-x", "c", "-c", str(archivo), "-o", str(objeto)]
        try:
            compilado = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=TIEMPO_LIMITE)
        except (OSError, subprocess.SubprocessError):
            return {}, COMPILA_ES_NECESARIO
        if compilado.returncode != 0:
            if opciones_abi:
                return {}, f"No se pudo compilar para {abi}: puede faltar el soporte de 32 bits de gcc o el código no compila."
            return {}, COMPILA_ES_NECESARIO
        layouts = _layouts_gdb(objeto, nombres, carpeta)
        if layouts is None:
            layouts = _layouts_pahole(objeto, nombres, abi)
        if layouts is None:
            return {}, "Faltan gdb y pahole: instalá gdb para que brett mida los tamaños reales (ver `brett doctor`)."
    return layouts, SIN_NOMBRE_VISIBLE
