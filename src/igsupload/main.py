from pathlib import Path
from typing import Optional

import typer
from igsupload.workflow import start
from igsupload.config import load_env
from igsupload.igsupload_logger import set_logging_path

app = typer.Typer(add_completion=False)

@app.command("intro")
def help_cmd():
    """
    Prints small introduction page for the user
    """
    typer.echo("\nIGS Uploader - Help & Troubleshooting\n")
    typer.echo("Usage:")
    typer.echo("  igsupload --csv /path/to/metadata.csv [--config /path/to/.env]\n")
    typer.echo("Typical problems and solutions:")
    typer.echo("1) ProxyError or 403 Forbidden")
    typer.echo("   → Your environment blocks requests to the DEMIS test environment.")
    typer.echo("   → Ensure correct network/proxy settings.\n")
    typer.echo("2) file not found")
    typer.echo("   → CSV path must exist locally.")
    typer.echo("   → Expected structure:")
    typer.echo("    my-dataset/\n    ├── metadata/\n    │   └── data.csv\n    └── reads/\n        ├── Sample1_R1.fastq\n        ├── Sample1_R2.fastq\n        └── ...\n")
    typer.echo("3) Validation failed: Hash does not match")
    typer.echo("   → File changed after hashing or repacked.\n")
    typer.echo("4) Invalid files")
    typer.echo("   → Wrong FASTA/FASTQ structure or CSV content.\n")
    typer.echo("Examples:")
    typer.echo("  igsupload --csv ./test_data/metadata/test_data.csv")
    typer.echo("  igsupload --csv ./data.csv --config ./secrets/.env")
    typer.echo("  igsupload intro\n")

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    csv: Optional[Path] = typer.Option(
        None, "--csv", help="Path to metadata CSV file", exists=False, show_default=False
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", help="Optional path to a .env file (overrides auto-detection)", exists=False, show_default=False
    ),
    log: Optional[Path] = typer.Option(
        None, "--log", help="Optional path to a log file. If not set it will be put into the root project dircetory", exists=False, show_default=False
    ),
):
    """
    Start the upload using --csv, optional --config and optional --log.
    """
    if ctx.invoked_subcommand is not None:
        return

    if csv is None:
        typer.echo(typer.style("Error: --csv is required.", fg=typer.colors.RED))
        typer.echo("Use: igsupload --csv /path/to/metadata.csv [--config /path/to/.env] [--log /path/to/log.csv]")
        raise typer.Exit(code=2)

    # Config laden
    try:
        cfg = load_env(config_path=config)
    except Exception as e:
        typer.echo(typer.style(f"Config error: {e}", fg=typer.colors.RED))
        raise typer.Exit(code=1)
    
    # set log file path
    set_logging_path(path=str(log))

    # CSV prüfen
    csv_path = csv.expanduser().resolve()
    if not csv_path.exists() or not csv_path.is_file():
        typer.echo(typer.style(f"Error: CSV path '{csv_path}' not found.", fg=typer.colors.RED))
        raise typer.Exit(code=2)

    typer.echo(f"[INFO] load CSV-file: {csv_path}")
    start(str(csv_path))


if __name__ == "__main__":
    app()
