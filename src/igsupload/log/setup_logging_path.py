import datetime

from pathlib import Path

from igsupload.utils.generate_code import get_four_digit_code

def setup_path(log_dir: Path | None = None) -> Path:
    if not log_dir:
        log_dir = Path("logging")

    date = datetime.datetime.now()
    date = date.strftime("%d-%m-%Y_%H-%M-%S")
    code = get_four_digit_code()
    dir_name = f"{date}_{code}"

    log_dir = Path(log_dir / dir_name)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir