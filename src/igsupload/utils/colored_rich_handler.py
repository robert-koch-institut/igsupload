import logging

from rich.logging import RichHandler
from rich.text import Text


class ColoredRichHandler(RichHandler):
    def render_message(
        self,
        record: logging.LogRecord,
        message: str,
    ) -> Text:

        text = super().render_message(record, message)

        color = getattr(record, "color", None)

        if color is None:
            color = {
                logging.WARNING: "yellow",
                logging.ERROR: "bold red",
                logging.CRITICAL: "bold white on red",
            }.get(record.levelno)

        if color:
            text.stylize(color)

        return text