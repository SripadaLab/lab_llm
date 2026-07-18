"""Small helpers for files stored through the OpenAI Files API."""
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Optional

from .config import get_client
from .privacy import Deidentifier


def upload_file(
    path: str | Path,
    *,
    deidentifier: Optional[Deidentifier] = None,
):
    """Upload a file, optionally filtering a UTF-8 text copy first."""
    path = Path(path)

    if deidentifier is not None:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "local de-identification supports UTF-8 text files; extract "
                "text from binary documents before uploading"
            ) from exc
        filtered = deidentifier.deidentify(text)
        file = BytesIO(filtered.text.encode("utf-8"))
        file.name = path.name
        with file:
            return get_client().files.create(file=file, purpose="user_data")

    # The SDK uploads bytes. The context manager closes the file after upload.
    with path.open("rb") as file:
        return get_client().files.create(file=file, purpose="user_data")


def delete_file(file_id: str):
    """Delete one uploaded file and return the API result."""
    if not isinstance(file_id, str) or not file_id.strip():
        raise ValueError("file_id must be a non-empty string")

    # Uploaded files are server-side objects. Remove them when no longer needed.
    return get_client().files.delete(file_id)


@contextmanager
def temporary_file(
    path: str | Path,
    *,
    deidentifier: Optional[Deidentifier] = None,
):
    """Upload one file, then delete it when the `with` block ends."""
    uploaded = upload_file(path, deidentifier=deidentifier)
    try:
        yield uploaded
    finally:
        delete_file(uploaded.id)
