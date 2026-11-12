import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from analizador_archivos import (
    file_hash,
    human_size,
    try_read_text,
    unique_destination_path,
)


class FileUtilityTests(unittest.TestCase):
    def test_human_size_uses_binary_units(self):
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(2048), "2.0 KB")
        self.assertEqual(human_size(5 * 1024 ** 3), "5.0 GB")

    def test_file_hash_reads_in_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.bin"
            payload = b"0123456789" * 100
            path.write_bytes(payload)

            digest, error = file_hash(str(path), chunk_size=17)

            self.assertIsNone(error)
            self.assertEqual(digest, hashlib.sha256(payload).hexdigest())

    def test_file_hash_returns_error_for_missing_file(self):
        digest, error = file_hash(os.path.join(tempfile.gettempdir(), "missing-file-analyzer-test.bin"))
        self.assertIsNone(digest)
        self.assertIn("No se pudo calcular el hash", error)

    def test_try_read_text_decodes_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "utf8.txt"
            path.write_text("Cádiz · análisis", encoding="utf-8")

            content, error = try_read_text(str(path), max_bytes=1024)

            self.assertIsNone(error)
            self.assertEqual(content, "Cádiz · análisis")

    def test_try_read_text_falls_back_to_latin1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.txt"
            path.write_bytes("café".encode("latin-1"))

            content, error = try_read_text(str(path), max_bytes=1024)

            self.assertIsNone(error)
            self.assertEqual(content, "café")

    def test_try_read_text_skips_files_over_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.txt"
            path.write_bytes(b"x" * 32)

            content, error = try_read_text(str(path), max_bytes=16)

            self.assertIsNone(content)
            self.assertIsNone(error)

    def test_unique_destination_path_preserves_extension_and_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "report.pdf").write_text("existing", encoding="utf-8")
            (root / "report (1).pdf").write_text("also existing", encoding="utf-8")

            candidate = unique_destination_path(tmp, "report.pdf")

            self.assertEqual(Path(candidate).name, "report (2).pdf")
            self.assertFalse(Path(candidate).exists())


if __name__ == "__main__":
    unittest.main()
