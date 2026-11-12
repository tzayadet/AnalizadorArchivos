import unittest

from csv_safety import csv_safe_cell


class CsvFormulaInjectionTests(unittest.TestCase):
    def test_formula_prefixes_are_neutralized(self):
        for value in ("=1+1", "+1+1", "-1+1", "@SUM(A1:A2)", "  =HYPERLINK(\"https://example.com\")"):
            with self.subTest(value=value):
                self.assertEqual(csv_safe_cell(value), "'" + value)

    def test_non_formula_values_are_unchanged(self):
        for value in ("normal.txt", "C:/Users/demo/file.pdf", "2026-11-12 10:00:00", ""):
            with self.subTest(value=value):
                self.assertEqual(csv_safe_cell(value), value)

    def test_non_string_values_remain_typed(self):
        self.assertEqual(csv_safe_cell(123), 123)
        self.assertIsNone(csv_safe_cell(None))


if __name__ == "__main__":
    unittest.main()
