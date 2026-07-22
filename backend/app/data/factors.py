from __future__ import annotations

import io
import re
import zipfile

import httpx
import pandas as pd

_BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"


class FrenchFactorProvider:
    """Loads the official monthly U.S. Fama–French five factors and momentum."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self._cached: pd.DataFrame | None = None

    def monthly_factors(self) -> pd.DataFrame:
        if self._cached is not None:
            return self._cached.copy()
        five = self._download_zip_csv("F-F_Research_Data_5_Factors_2x3_CSV.zip")
        momentum = self._download_zip_csv("F-F_Momentum_Factor_CSV.zip")
        momentum_column = next(
            (column for column in momentum.columns if column.strip().lower().startswith("mom")),
            momentum.columns[0],
        )
        momentum = momentum[[momentum_column]].rename(columns={momentum_column: "MOM"})
        frame = five.join(momentum, how="inner")
        frame.columns = [
            str(column).strip().replace("Mkt-RF", "MKT_RF") for column in frame.columns
        ]
        self._cached = frame.apply(pd.to_numeric, errors="coerce").dropna() / 100.0
        return self._cached.copy()

    def _download_zip_csv(self, filename: str) -> pd.DataFrame:
        response = httpx.get(f"{_BASE_URL}/{filename}", timeout=self.timeout, follow_redirects=True)
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            member = archive.namelist()[0]
            text = archive.read(member).decode("utf-8", errors="replace")
        return _parse_monthly_factor_text(text)


def _parse_monthly_factor_text(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    rows: list[str] = []
    header: str | None = None
    for line in lines:
        stripped = line.strip()
        if header is None and stripped.startswith(","):
            header = stripped
            continue
        if re.match(r"^\d{6},", stripped):
            rows.append(stripped)
        elif rows:
            break
    if header is None or not rows:
        raise ValueError("Unexpected Kenneth French factor file format")
    frame = pd.read_csv(io.StringIO("date" + header + "\n" + "\n".join(rows)))
    frame["date"] = (
        pd.to_datetime(frame["date"].astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    )
    return frame.set_index("date")
