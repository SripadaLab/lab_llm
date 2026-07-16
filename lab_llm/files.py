"""Small helpers for files stored through the OpenAI Files API."""
from pathlib import Path

from .config import get_client


def upload_file(path: str | Path):
    """Upload one local file for model input and return its File object."""
    path = Path(path)

    # The SDK uploads bytes. The context manager closes the file after upload.
    with path.open("rb") as file:
        return get_client().files.create(file=file, purpose="user_data")


def delete_file(file_id: str):
    """Delete one uploaded file and return the API result."""
    if not isinstance(file_id, str) or not file_id.strip():
        raise ValueError("file_id must be a non-empty string")

    # Uploaded files are server-side objects. Remove them when no longer needed.
    return get_client().files.delete(file_id)
