"""CLI de BRETT — Auditor de alineación y padding de estructuras en C."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from brett import __version__
from brett.core.padding import auditar_rutas

console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name="brett",
    help="📏 BRETT — Auditor de alineación y padding de estructuras C y optimizador de reordenamiento de campos.",
    add_completion=True,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold cyan]BRETT[/bold cyan] versión [bold]{__version__}[/bold]")
        raise typer.Exit(code=0)


@app.callback()
def main_callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Muestra la versión de BRETT.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    pass


@app.command("audit")
def audit_cmd(
    rutas: List[Path] = typer.Argument(..., help="Archivos C/H o directorios a auditar."),
    json_output: bool = typer.Option(False, "--json", help="Emitir reporte en JSON."),
) -> None:
    """Audita estructuras en busca de bytes de memoria desperdiciados por desalineación y padding."""
    reporte = auditar_rutas(rutas)

    if json_output:
        print(json.dumps(reporte.to_dict(), indent=2, ensure_ascii=False))
        raise typer.Exit(code=0)

    if not reporte.structs:
        console.print("[green]No se encontraron declaraciones de 'typedef struct' en los archivos analizados.[/green]")
        raise typer.Exit(code=0)

    tabla = Table(title=f"Auditoría de Padding de Estructuras ({len(reporte.structs)} structs)")
    tabla.add_column("Estructura", style="bold cyan")
    tabla.add_column("Ubicación", style="yellow")
    tabla.add_column("Tamaño Actual", justify="right")
    tabla.add_column("Datos Útiles", justify="right")
    tabla.add_column("Padding", justify="right", style="red")
    tabla.add_column("Optimizado", justify="right", style="green")
    tabla.add_column("Ahorro", justify="right", style="bold green")

    for s in reporte.structs:
        ahorro_str = f"-{s.bytes_ahorrados} B" if s.bytes_ahorrados > 0 else "0 B"
        tabla.add_row(
            s.nombre,
            f"{s.archivo.name}:{s.linea}",
            f"{s.tamanio_total_bytes} B",
            f"{s.tamanio_datos_utiles_bytes} B",
            f"{s.bytes_padding_desperdiciados} B",
            f"{s.tamanio_optimizado_bytes} B",
            ahorro_str,
        )

    console.print(tabla)

    color = "green" if reporte.total_bytes_ahorrables == 0 else "yellow"
    console.print(Panel(
        f"Total structs: [bold]{len(reporte.structs)}[/bold] · "
        f"Bytes de padding totales: [red]{reporte.total_bytes_desperdiciados} B[/red] · "
        f"Bytes ahorrables reordenando: [bold green]{reporte.total_bytes_ahorrables} B[/bold green]",
        title="Resumen de Padding",
        border_style=color,
    ))


@app.command("optimize")
def optimize_cmd(
    archivo: Path = typer.Argument(..., help="Archivo C/H con las estructuras a optimizar."),
) -> None:
    """Genera el código C optimizado reordenando los campos de menor a mayor alineación."""
    reporte = auditar_rutas([archivo])
    if not reporte.structs:
        console.print("[yellow]No se encontraron estructuras para optimizar.[/yellow]")
        raise typer.Exit(code=0)

    for s in reporte.structs:
        console.print(f"\n[bold cyan]Estructura: {s.nombre}[/bold cyan] ({s.archivo.name}:{s.linea})")
        console.print(Panel(
            Syntax(s.codigo_optimizado, "c", theme="monokai", line_numbers=True),
            title=f"Layout Sugerido ({s.tamanio_total_bytes} B ➔ {s.tamanio_optimizado_bytes} B)",
            border_style="green",
        ))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
