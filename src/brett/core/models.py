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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_structs": len(self.structs),
            "total_bytes_desperdiciados": self.total_bytes_desperdiciados,
            "total_bytes_ahorrables": self.total_bytes_ahorrables,
            "structs": [s.to_dict() for s in self.structs],
        }
