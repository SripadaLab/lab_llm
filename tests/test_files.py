"""Tests for the small Files API helpers."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lab_llm import delete_file, upload_file


class FileTests(TestCase):
    def test_uploads_a_local_file_as_user_data(self):
        uploaded = SimpleNamespace(id="file_test")
        files = SimpleNamespace(create=Mock(return_value=uploaded))
        client = SimpleNamespace(files=files)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("research notes", encoding="utf-8")

            with patch("lab_llm.files.get_client", return_value=client):
                result = upload_file(path)

        self.assertIs(result, uploaded)
        supplied_file = files.create.call_args.kwargs["file"]
        self.assertTrue(supplied_file.closed)
        self.assertEqual(files.create.call_args.kwargs["purpose"], "user_data")

    def test_deletes_a_file_and_rejects_invalid_ids(self):
        deleted = SimpleNamespace(id="file_test", deleted=True)
        files = SimpleNamespace(delete=Mock(return_value=deleted))
        client = SimpleNamespace(files=files)

        with patch("lab_llm.files.get_client", return_value=client):
            self.assertIs(delete_file("file_test"), deleted)

        files.delete.assert_called_once_with("file_test")

        for file_id in ("", "   ", None):
            with self.subTest(file_id=file_id):
                with self.assertRaisesRegex(ValueError, "file_id"):
                    delete_file(file_id)
