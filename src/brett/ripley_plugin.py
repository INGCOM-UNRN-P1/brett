"""Plugin de BRETT para integración con RIPLEY."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from brett.core.padding import auditar_rutas


class BrettPlugin:
    """Plugin de auditoría de padding de structs para Ripley."""

    name = "padding"
    version = "0.1.0"

    def is_available(self) -> bool:
        return True

    def execute(self, workspace: Path, manifest_config: Dict[str, Any]) -> Dict[str, Any]:
        reporte = auditar_rutas([workspace])
        observaciones = []

        for s in reporte.structs:
            if s.bytes_ahorrados > 0:
                observaciones.append({
                    "codigo": "PADDING_INEFFICIENT",
                    "severidad": "WARNING",
                    "archivo": str(s.archivo),
                    "linea": s.linea,
                    "mensaje": f"Estructura '{s.nombre}' desperdicia {s.bytes_padding_desperdiciados} bytes de padding (se pueden ahorrar {s.bytes_ahorrados} bytes).",
                    "sugerencia": s.codigo_optimizado,
                })

        return {
            "ok": len(observaciones) == 0,
            "total_structs": len(reporte.structs),
            "total_bytes_desperdiciados": reporte.total_bytes_desperdiciados,
            "total_bytes_ahorrables": reporte.total_bytes_ahorrables,
            "observaciones": observaciones,
        }
