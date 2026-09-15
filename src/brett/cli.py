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


def generar_seccion_markdown(reporte) -> str:
    """Genera sección de auditoría de padding y estructuras para Dredd."""
    lines = [
        "<!-- dredd-section: brett v1.0.0 -->\n",
        "## Auditoría de Padding y Structs (Brett)\n",
    ]
    lines.append(f"- **Structs analizados:** {len(reporte.structs)}")
    lines.append(f"- **Padding total desperdiciado:** {reporte.total_bytes_desperdiciados} B")
    lines.append(f"- **Bytes ahorrables:** {reporte.total_bytes_ahorrables} B\n")
    if not reporte.structs:
        lines.append("> [!NOTE]\n> No se encontraron declaraciones de estructuras (`struct`) en los archivos analizados.\n")
    elif reporte.total_bytes_ahorrables == 0:
        lines.append("> [!TIP]\n> **Alineación Óptima:** Las estructuras analizadas no presentan desperdicio de memoria por padding innecesario.\n")
    else:
        lines.append("| Estructura | Ubicación | Tamaño Actual | Útil | Padding | Optimizado | Ahorro Potencial |")
        lines.append("| :--- | :--- | :---: | :---: | :---: | :---: | :---: |")
        for s in reporte.structs:
            ahorro_str = f"**-{s.bytes_ahorrados} B**" if s.bytes_ahorrados > 0 else "0 B"
            nom_limpio = s.nombre.replace("|", "&#124;")
            loc_limpio = f"{s.archivo.name}:{s.linea}".replace("|", "&#124;")
            lines.append(f"| `{nom_limpio}` | `{loc_limpio}` | {s.tamanio_total_bytes} B | {s.tamanio_datos_utiles_bytes} B | {s.bytes_padding_desperdiciados} B | {s.tamanio_optimizado_bytes} B | {ahorro_str} |")
        lines.append("")
    return "\n".join(lines)


@app.command("audit")
def audit_cmd(
    rutas: List[Path] = typer.Argument(..., help="Archivos C/H o directorios a auditar."),
    json_output: bool = typer.Option(False, "--json", help="Emitir reporte en JSON."),
    output_md: Optional[Path] = typer.Option(None, "--md", "--output-md", "-o", help="Generar sección de reporte en formato Markdown para fusión en Dredd."),
) -> None:
    """Audita estructuras en busca de bytes de memoria desperdiciados por desalineación y padding."""
    reporte = auditar_rutas(rutas)

    if output_md:
        md_text = generar_seccion_markdown(reporte)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(md_text, encoding="utf-8")
        console.print(f"[green]✓ Sección Markdown generada en:[/green] [cyan]{output_md}[/cyan]")
        raise typer.Exit(code=0)

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


@app.command("report")
def report_cmd(
    rutas: List[Path] = typer.Argument(..., help="Archivos C/H o directorios a auditar."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de destino del archivo Markdown."),
) -> None:
    """Genera directamente la sección de reporte Markdown de BRETT para Dredd."""
    reporte = auditar_rutas(rutas)
    md_content = generar_seccion_markdown(reporte)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(md_content, encoding="utf-8")
        console.print(f"[green]✓ Reporte Markdown generado en:[/green] [cyan]{output}[/cyan]")
    else:
        print(md_content)


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


@app.command("doctor")
def doctor_cmd(
    json_output: bool = typer.Option(False, "--json", help="Emitir diagnóstico en formato JSON estructurado."),
) -> None:
    """Verifica el estado del entorno de auditoría de memoria y padding BRETT (Tree-Sitter C, Python, GCC)."""
    import shutil
    import sys
    diagnostico = []

    py_ok = sys.version_info >= (3, 10)
    diagnostico.append({
        "componente": "Python Runtime",
        "estado": "OK" if py_ok else "ERROR",
        "requerido": True,
        "detalle": f"Python {sys.version.split()[0]}",
    })

    ts_ok = False
    try:
        from brett.core.padding import get_c_parser
        get_c_parser()
        ts_ok = True
        ts_det = "Parser Tree-Sitter C y gramática AST operativos"
    except Exception as e:
        ts_det = str(e)
    diagnostico.append({
        "componente": "Tree-Sitter C Parser",
        "estado": "OK" if ts_ok else "ERROR",
        "requerido": True,
        "detalle": ts_det,
    })

    gcc_path = shutil.which("gcc")
    diagnostico.append({
        "componente": "Compilador GCC",
        "estado": "OK" if gcc_path else "ADVERTENCIA",
        "requerido": False,
        "detalle": gcc_path or "No encontrado (opcional para verificación ABI nativa)",
    })

    todo_ok = py_ok and ts_ok

    if json_output:
        payload = {
            "schema_version": "1.0.0",
            "herramienta": "brett",
            "ok": todo_ok,
            "componentes": diagnostico,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0 if todo_ok else 1)

    tabla = Table(title="🏥 Diagnóstico del Entorno BRETT (doctor)", border_style="cyan")
    tabla.add_column("Componente", style="bold white")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Detalle")

    for c in diagnostico:
        color = "bold green" if c["estado"] == "OK" else ("bold yellow" if c["estado"] == "ADVERTENCIA" else "bold red")
        simbolo = "✓" if c["estado"] == "OK" else ("⚠️" if c["estado"] == "ADVERTENCIA" else "✗")
        tabla.add_row(c["componente"], f"[{color}]{simbolo} {c['estado']}[/{color}]", c["detalle"])

    console.print(tabla)
    if not todo_ok:
        raise typer.Exit(code=1)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
