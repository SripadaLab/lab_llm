"""Tests for the small Files API helpers."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from lab_llm import (
    DeidentificationResult,
    IdentifierMatch,
    delete_file,
    temporary_file,
    upload_file,
)


class FakeDeidentifier:
    def deidentify(self, text):
        match = IdentifierMatch(
            label="private_person",
            start=0,
            end=len("Alice Smith"),
            original="Alice Smith",
            replacement="[PRIVATE_PERSON_1]",
        )
        return DeidentificationResult(
            text=text.replace("Alice Smith", "[PRIVATE_PERSON_1]"),
            matches=(match,) if "Alice Smith" in text else (),
        )


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

    def test_uploads_only_an_in_memory_deidentified_text_copy(self):
        uploaded = SimpleNamespace(id="file_test")
        captured = {}

        def create(*, file, purpose):
            captured["name"] = file.name
            captured["bytes"] = file.read()
            captured["purpose"] = purpose
            return uploaded

        client = SimpleNamespace(files=SimpleNamespace(create=create))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("Met Alice Smith", encoding="utf-8")

            with patch("lab_llm.files.get_client", return_value=client):
                result = upload_file(
                    path,
                    deidentifier=FakeDeidentifier(),
                )

            self.assertEqual(path.read_text(), "Met Alice Smith")

        self.assertIs(result, uploaded)
        self.assertEqual(captured["name"], "notes.txt")
        self.assertEqual(captured["purpose"], "user_data")
        self.assertEqual(captured["bytes"], b"Met [PRIVATE_PERSON_1]")
        self.assertNotIn(b"Alice Smith", captured["bytes"])

    def test_temporary_file_is_deleted_after_an_error(self):
        uploaded = SimpleNamespace(id="file_test")
        files = SimpleNamespace(
            create=Mock(return_value=uploaded),
            delete=Mock(return_value=SimpleNamespace(deleted=True)),
        )
        client = SimpleNamespace(files=files)

        with TemporaryDirectory() as directory:
            path = Path(directory) / "notes.txt"
            path.write_text("research notes", encoding="utf-8")

            with patch("lab_llm.files.get_client", return_value=client):
                with self.assertRaisesRegex(RuntimeError, "model failed"):
                    with temporary_file(path) as result:
                        self.assertIs(result, uploaded)
                        raise RuntimeError("model failed")

        files.delete.assert_called_once_with("file_test")
