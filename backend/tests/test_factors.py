from __future__ import annotations

import pytest

from app.data.factors import _parse_monthly_factor_text


def test_parse_kenneth_french_monthly_section() -> None:
    text = """This file was created for testing
,Mkt-RF,SMB,HML,RF
202001,1.20,-0.30,0.50,0.10
202002,-2.10,0.40,-0.20,0.10

 Annual Factors: January-December
"""

    result = _parse_monthly_factor_text(text)

    assert list(result.columns) == ["Mkt-RF", "SMB", "HML", "RF"]
    assert result.index[0].strftime("%Y-%m-%d") == "2020-01-31"
    assert result.iloc[1]["Mkt-RF"] == pytest.approx(-2.10)


def test_parse_kenneth_french_rejects_unexpected_format() -> None:
    with pytest.raises(ValueError, match="Unexpected Kenneth French"):
        _parse_monthly_factor_text("no monthly table here")
