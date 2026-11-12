"""CSV output safeguards for spreadsheet applications."""


FORMULA_PREFIXES = ("=", "+", "-", "@")


def csv_safe_cell(value):
    """Prefix potentially executable spreadsheet formulas with an apostrophe."""
    if not isinstance(value, str):
        return value
    if value.lstrip(" \t\r\n").startswith(FORMULA_PREFIXES):
        return "'" + value
    return value
