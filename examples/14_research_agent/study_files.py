"""Read-only access to one fixed synthetic study."""
from pathlib import Path


STUDY_PATH = Path(__file__).with_name("study")
READABLE_SUFFIXES = {".csv", ".json", ".md", ".txt"}
MAX_FILE_CHARACTERS = 20_000


def list_study_files(study_path: str | Path = STUDY_PATH) -> list[dict]:
    """Return the readable files below one fixed study folder."""
    root = Path(study_path).resolve()
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "characters": len(path.read_text(encoding="utf-8")),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix.lower() in READABLE_SUFFIXES
    ]


def read_study_file(
    path: str,
    study_path: str | Path = STUDY_PATH,
) -> str:
    """Read one allowed file without escaping the fixed study folder."""
    root = Path(study_path).resolve()
    target = (root / path).resolve()

    if target == root or root not in target.parents:
        raise ValueError("Path must stay inside the study folder.")
    if not target.is_file():
        raise ValueError(f"Study file not found: {path}")
    if target.suffix.lower() not in READABLE_SUFFIXES:
        raise ValueError(f"Unsupported study file: {path}")

    text = target.read_text(encoding="utf-8")
    if len(text) > MAX_FILE_CHARACTERS:
        raise ValueError(
            f"{path} is too large for this demo "
            f"({len(text):,} characters)."
        )
    return text
