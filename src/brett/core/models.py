"""Modelos de datos para el cálculo y auditoría de padding en BRETT."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CampoStruct:
    """Representa un miembro dentro de un struct C."""
    tipo: str
    nombre: str
    tamanio: int
    alineacion: int
    offset_original: int
    offset_optimizado: int = 0
    # Sufijo de declarador de arreglo tal como aparece en el fuente ("[10]",
    # "[3][4]"); se preserva al emitir el código reordenado para no cambiar la
    # semántica del programa del estudiante.
    sufijo_array: str = ""
    # True cuando alguna dimensión no es un literal entero (p. ej. `int v[MAX]`)
    # y por lo tanto el tamaño del campo no se puede calcular con exactitud.
    dimension_no_resuelta: bool = False

    @property
    def declaracion(self) -> str:
        """Declaración del campo tal como debe emitirse en C."""
        return f"{self.tipo} {self.nombre}{self.sufijo_array}"


@dataclass
class StructInfo:
    """Información completa del layout de memoria de un struct."""
    nombre: str
    archivo: Path
    linea: int
    campos: List[CampoStruct] = field(default_factory=list)
    tamanio_total_bytes: int = 0
    tamanio_datos_utiles_bytes: int = 0
    bytes_padding_desperdiciados: int = 0
    tamanio_optimizado_bytes: int = 0
    bytes_ahorrados: int = 0
    codigo_optimizado: str = ""

    @property
    def tiene_dimensiones_no_resueltas(self) -> bool:
        """True si algún campo es un arreglo de dimensión no literal."""
        return any(c.dimension_no_resuelta for c in self.campos)

    @property
    def mensaje(self) -> str:
        """Descripción del hallazgo, apta tanto para el alumno como para Ripley."""
        if self.bytes_ahorrados > 0:
            return (
                f"Estructura '{self.nombre}' desperdicia {self.bytes_padding_desperdiciados} "
                f"bytes de padding; reordenando sus campos se ahorran {self.bytes_ahorrados} bytes."
            )
        return (
            f"Estructura '{self.nombre}' ya tiene un layout óptimo "
            f"({self.bytes_padding_desperdiciados} B de padding son inevitables por alineación)."
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "archivo": str(self.archivo),
            "linea": self.linea,
            "total_campos": len(self.campos),
            "tamanio_actual_bytes": self.tamanio_total_bytes,
            "tamanio_datos_bytes": self.tamanio_datos_utiles_bytes,
            "bytes_padding": self.bytes_padding_desperdiciados,
            "tamanio_optimizado_bytes": self.tamanio_optimizado_bytes,
            "bytes_ahorrados": self.bytes_ahorrados,
            "codigo_optimizado": self.codigo_optimizado,
            "dimensiones_no_resueltas": self.tiene_dimensiones_no_resueltas,
            # Claves del contrato de satélite de Ripley (`normalize_finding`), que
            # sin ellas degrada el hallazgo a un mensaje vacío. `wasted_padding_bytes`
            # lleva el ahorro reordenable —no el padding total— porque es lo que
            # decide la severidad: el padding inevitable por alineación no es un
            # defecto que el alumno pueda corregir.
            "name": self.nombre,
            "wasted_padding_bytes": self.bytes_ahorrados,
            "message": self.mensaje,
            "suggestion": self.codigo_optimizado if self.bytes_ahorrados > 0 else "",
            "file_path": str(self.archivo),
            "line_number": self.linea,
        }


@dataclass
class ReportePadding:
    """Reporte consolidado de auditoría de padding sobre un conjunto de archivos."""
    structs: List[StructInfo] = field(default_factory=list)

    @property
    def total_bytes_desperdiciados(self) -> int:
        return sum(s.bytes_padding_desperdiciados for s in self.structs)

    @property
    def total_bytes_ahorrables(self) -> int:
        return sum(s.bytes_ahorrados for s in self.structs)

    @property
    def ok(self) -> bool:
        """True si no hay padding reordenable en ninguna estructura."""
        return self.total_bytes_ahorrables == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            # Ripley deriva el veredicto de `ok`/`passed`; sin estas claves asumía
            # True y daba por aprobado un proyecto con bytes desperdiciados.
            "ok": self.ok,
            "passed": self.ok,
            "total_structs": len(self.structs),
            "total_bytes_desperdiciados": self.total_bytes_desperdiciados,
            "total_bytes_ahorrables": self.total_bytes_ahorrables,
            "structs": [s.to_dict() for s in self.structs],
        }
