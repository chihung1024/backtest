from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class RebalanceFrequency(StrEnum):
    NONE = "none"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMIANNUAL = "semiannual"
    ANNUAL = "annual"


class CashflowFrequency(StrEnum):
    NONE = "none"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class CashflowType(StrEnum):
    NONE = "none"
    FIXED = "fixed"
    PERCENT = "percent"


class LeverageType(StrEnum):
    NONE = "none"
    FIXED_RATIO = "fixed_ratio"
    FIXED_DEBT = "fixed_debt"


class RegimeType(StrEnum):
    NONE = "none"
    MARKET = "market"
    VOLATILITY = "volatility"
    INFLATION = "inflation"
    BUSINESS_CYCLE = "business_cycle"


class OutputFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


TickerSymbol = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=32),
]


class AssetAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: TickerSymbol
    weight: float = Field(gt=0, le=100)


class PortfolioDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=60)
    assets: list[AssetAllocation] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_allocations(self) -> PortfolioDefinition:
        symbols = [asset.symbol for asset in self.assets]
        if len(symbols) != len(set(symbols)):
            raise ValueError("A portfolio cannot contain the same ticker more than once")
        total = sum(asset.weight for asset in self.assets)
        if abs(total - 100.0) > 0.05:
            raise ValueError(f"Portfolio weights must total 100%, received {total:.2f}%")
        return self


class CashflowConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: CashflowType = CashflowType.NONE
    amount: float = 0.0
    frequency: CashflowFrequency = CashflowFrequency.NONE
    timing: str = Field(default="end", pattern="^(beginning|end)$")
    annual_growth_rate: float = Field(default=0.0, ge=-100, le=100)

    @model_validator(mode="after")
    def validate_cashflow(self) -> CashflowConfig:
        if self.type != CashflowType.NONE and self.frequency == CashflowFrequency.NONE:
            raise ValueError("Cashflow frequency is required when cashflows are enabled")
        return self


class RebalanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: RebalanceFrequency = RebalanceFrequency.ANNUAL
    threshold_percent: float | None = Field(default=None, gt=0, le=100)


class LeverageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: LeverageType = LeverageType.NONE
    ratio: float = Field(default=1.0, ge=1.0, le=5.0)
    debt_amount: float = Field(default=0.0, ge=0.0)
    annual_interest_rate: float = Field(default=0.0, ge=0.0, le=100.0)
    maintenance_margin: float = Field(default=25.0, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_leverage(self) -> LeverageConfig:
        if self.type == LeverageType.FIXED_RATIO and self.ratio <= 1:
            raise ValueError("Fixed-ratio leverage must be greater than 1")
        if self.type == LeverageType.FIXED_DEBT and self.debt_amount <= 0:
            raise ValueError("Fixed debt amount must be greater than zero")
        return self


class AnalyticsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style_analysis: bool = False
    factor_regression: bool = False
    regime: RegimeType = RegimeType.NONE
    risk_free_rate: float = Field(default=0.0, ge=-20.0, le=100.0)
    inflation_adjusted: bool = False


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolios: list[PortfolioDefinition] = Field(min_length=1, max_length=3)
    benchmark: TickerSymbol | None = None
    start_date: date
    end_date: date
    initial_amount: float = Field(default=10_000.0, gt=0, le=1_000_000_000_000)
    base_currency: Literal["TWD"] = "TWD"
    include_ytd: bool = True
    reinvest_dividends: bool = True
    display_income: bool = True
    transaction_cost_bps: float = Field(default=0.0, ge=0.0, le=1_000.0)
    cashflow: CashflowConfig = Field(default_factory=CashflowConfig)
    rebalancing: RebalanceConfig = Field(default_factory=RebalanceConfig)
    leverage: LeverageConfig = Field(default_factory=LeverageConfig)
    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)
    output_frequency: OutputFrequency = OutputFrequency.DAILY

    @model_validator(mode="after")
    def validate_dates(self) -> BacktestRequest:
        if self.start_date >= self.end_date:
            raise ValueError("Start date must be before end date")
        if self.end_date > date.today():
            raise ValueError("End date cannot be in the future")
        return self

    @property
    def symbols(self) -> list[str]:
        values = {asset.symbol for portfolio in self.portfolios for asset in portfolio.assets}
        if self.benchmark:
            values.add(self.benchmark)
        return sorted(values)


class AssetMetadata(BaseModel):
    symbol: str
    name: str
    currency: str
    first_date: date
    last_date: date
    observations: int
    dividend_events: int = 0
    capital_gain_events: int = 0
    split_events: int = 0
    repaired_observations: int = 0
    split_corrections: int = 0


class PerformancePoint(BaseModel):
    date: date
    value: float
    return_index: float
    drawdown: float
    cumulative_income: float


class PortfolioResult(BaseModel):
    name: str
    metrics: dict[str, float | int | str | None]
    series: list[PerformancePoint]
    annual_returns: dict[str, float]
    monthly_returns: list[dict[str, Any]]
    income_by_year: dict[str, float]
    final_allocation: dict[str, float]
    factor_analysis: dict[str, Any] | None = None
    style_analysis: dict[str, Any] | None = None
    regime_analysis: dict[str, Any] | None = None


class BacktestResponse(BaseModel):
    request_id: str
    generated_at: str
    data_as_of: date
    effective_start: date
    effective_end: date
    base_currency: Literal["TWD"]
    results: list[PortfolioResult]
    benchmark: PortfolioResult | None = None
    assets: list[AssetMetadata]
    warnings: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    quote_type: str | None = None
    currency: str | None = None
