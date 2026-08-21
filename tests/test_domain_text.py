import pytest

from quati.domain.job import clean_text, safe_table_text


def test_clean_text_keeps_words_separated_when_controls_are_removed() -> None:
    assert clean_text("Python\nSQL\x00Linux\u200b") == "Python SQL Linux"


def test_clean_text_normalizes_unicode_and_rejects_non_text() -> None:
    assert clean_text("Ａｎａｌｉｓｔａ") == "Analista"
    with pytest.raises(ValueError, match="Texto inválido"):
        clean_text(123)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["=1+1", "+cmd", "-2+3", "@SUM(A1:A2)"])
def test_table_text_neutralizes_spreadsheet_formulas(value: str) -> None:
    assert safe_table_text(value).startswith("'")
