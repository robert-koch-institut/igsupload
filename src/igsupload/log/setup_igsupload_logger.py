import logging
import sys
from pathlib import Path

from rich.console import Console

from igsupload.log.setup_logging_path import setup_path
from igsupload.utils.colored_rich_handler import ColoredRichHandler


def setup_logging(log_dir: Path | None = None) -> Path:
    log_dir = setup_path(log_dir)
    
    logger = logging.getLogger("igsupload")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Console output
    console = Console(file=sys.stdout)
    console_handler = ColoredRichHandler(
        console=console,
        level=logging.INFO,
        show_time=False,
        show_level=False,
        show_path=False,
        markup=False,
    )

    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s]: %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    # File output
    file_handler = logging.FileHandler(
        log_dir / "igsupload.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] "
            "[%(name)s] %(message)s"
        )
    )

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return log_dir