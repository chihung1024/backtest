from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from app.config import Settings
from app.data.factors import FrenchFactorProvider
from app.data.fred import FredProvider
from app.data.yfinance_provider import YFinanceProvider, normalize_symbol
from app.engine.analytics import (
    STYLE_PROXIES,
    factor_regression,
    regime_performance,
    returns_based_style,
)
from app.engine.backtest import align_histories, simulate_portfolio, to_portfolio_result
from app.models import (
    AssetMetadata,
    BacktestRequest,
    BacktestResponse,
    LeverageConfig,
    PortfolioDefinition,
    RegimeType,
)


class BacktestService:
    def __init__(self, settings: Settings, provider: YFinanceProvider | None = None) -> None:
        self.settings = settings
        self.provider = provider or YFinanceProvider(settings.cache_ttl_seconds)
        self.factor_provider = FrenchFactorProvider()

    def run(self, original_request: BacktestRequest) -> BacktestResponse:
        request, normalization_warnings = _normalized_request(original_request)
        if len(request.symbols) > self.settings.max_assets_per_request:
            raise ValueError(
                "A request can contain at most "
                f"{self.settings.max_assets_per_request} unique assets"
            )

        histories = self.provider.histories(
            request.symbols,
            request.start_date,
            request.end_date,
            request.base_currency,
        )
        # Successful market-data reconciliation is audit metadata, not a user-facing
        # error condition. Results continue normally after deterministic repair.
        warnings = list(normalization_warnings)
        aligned = align_histories(histories, request.symbols)
        if aligned.start > request.start_date:
            warnings.append(
                f"Common start moved to {aligned.start.isoformat()} because of "
                "asset inception dates"
            )
        if aligned.end < request.end_date:
            warnings.append(
                f"Common end moved to {aligned.end.isoformat()} because markets "
                "were closed or data ended"
            )

        simulations = [
            simulate_portfolio(portfolio, aligned, request) for portfolio in request.portfolios
        ]
        for simulation in simulations:
            warnings.extend(f"{simulation.name}: {item}" for item in simulation.warnings)

        benchmark_simulation = None
        benchmark_result = None
        if request.benchmark:
            benchmark_definition = PortfolioDefinition(
                name=f"Benchmark · {request.benchmark}",
                assets=[{"symbol": request.benchmark, "weight": 100.0}],
            )
            benchmark_request = request.model_copy(
                update={
                    "leverage": LeverageConfig(),
                    "transaction_cost_bps": 0.0,
                }
            )
            benchmark_simulation = simulate_portfolio(
                benchmark_definition, aligned, benchmark_request
            )

        style_histories = histories
        if request.analytics.style_analysis:
            try:
                style_histories = {
                    **histories,
                    **self.provider.histories(
                        list(STYLE_PROXIES.values()),
                        request.start_date,
                        request.end_date,
                        request.base_currency,
                    ),
                }
            except Exception as exc:
                warnings.append(f"Style analysis unavailable: {exc}")

        fred = None
        inflation_index = None
        needs_fred = request.analytics.inflation_adjusted or request.analytics.regime in {
            RegimeType.INFLATION,
            RegimeType.BUSINESS_CYCLE,
        }
        if needs_fred:
            if self.settings.fred_api_key:
                fred = FredProvider(self.settings.fred_api_key)
            else:
                warnings.append(
                    "Inflation-adjusted returns and macroeconomic regimes require "
                    "BACKTEST_FRED_API_KEY"
                )
        if request.analytics.inflation_adjusted and fred is not None:
            try:
                inflation_index = fred.series(
                    "CPIAUCSL",
                    request.start_date - timedelta(days=45),
                    request.end_date,
                )
                if request.base_currency != "USD":
                    warnings.append(
                        "Real returns use the U.S. CPI (CPIAUCSL), even when the selected "
                        f"base currency is {request.base_currency}"
                    )
            except Exception as exc:
                warnings.append(f"Inflation-adjusted returns unavailable: {exc}")

        if benchmark_simulation is not None:
            benchmark_result = to_portfolio_result(
                benchmark_simulation,
                benchmark_request,
                inflation_index=inflation_index,
                is_benchmark=True,
            )

        results = []
        for simulation in simulations:
            factor = None
            style = None
            regime = None
            if request.analytics.factor_regression:
                if request.base_currency != "USD":
                    warnings.append(
                        f"{simulation.name}: U.S. factor regression is available "
                        "only in USD base currency"
                    )
                else:
                    try:
                        factor = factor_regression(simulation, self.factor_provider)
                    except Exception as exc:
                        warnings.append(f"{simulation.name}: factor regression unavailable: {exc}")
            if request.analytics.style_analysis:
                try:
                    style = returns_based_style(simulation, style_histories)
                except Exception as exc:
                    warnings.append(f"{simulation.name}: style analysis unavailable: {exc}")
            if request.analytics.regime != RegimeType.NONE:
                regime_benchmark = benchmark_simulation or simulations[0]
                try:
                    regime = regime_performance(
                        simulation,
                        regime_benchmark,
                        request.analytics.regime,
                        fred,
                    )
                except Exception as exc:
                    warnings.append(f"{simulation.name}: regime analysis unavailable: {exc}")

            results.append(
                to_portfolio_result(
                    simulation,
                    request,
                    benchmark_simulation.daily_returns if benchmark_simulation else None,
                    factor_analysis=factor,
                    style_analysis=style,
                    regime_analysis=regime,
                    inflation_index=inflation_index,
                )
            )

        metadata = [
            AssetMetadata(
                symbol=symbol,
                name=histories[symbol].name,
                currency=histories[symbol].currency,
                first_date=histories[symbol].first_date,
                last_date=histories[symbol].last_date,
                observations=int(histories[symbol].total_returns.notna().sum()),
                dividend_events=histories[symbol].dividend_events,
                capital_gain_events=histories[symbol].capital_gain_events,
                split_events=histories[symbol].split_events,
                repaired_observations=histories[symbol].repaired_observations,
                split_corrections=histories[symbol].split_corrections,
            )
            for symbol in request.symbols
        ]
        return BacktestResponse(
            request_id=str(uuid4()),
            generated_at=datetime.now(UTC).isoformat(),
            data_as_of=aligned.end,
            effective_start=aligned.start,
            effective_end=aligned.end,
            base_currency=request.base_currency,
            results=results,
            benchmark=benchmark_result,
            assets=metadata,
            warnings=list(dict.fromkeys(warnings)),
        )


def _normalized_request(request: BacktestRequest) -> tuple[BacktestRequest, list[str]]:
    payload = request.model_dump(mode="python")
    warnings: list[str] = []
    for portfolio in payload["portfolios"]:
        for asset in portfolio["assets"]:
            original = asset["symbol"]
            normalized = normalize_symbol(original)
            asset["symbol"] = normalized
            if original != normalized:
                warnings.append(f"Normalized {original} to {normalized}")
    if payload.get("benchmark"):
        original = payload["benchmark"]
        normalized = normalize_symbol(original)
        payload["benchmark"] = normalized
        if original != normalized:
            warnings.append(f"Normalized benchmark {original} to {normalized}")
    today = date.today()
    if not payload["include_ytd"] and payload["end_date"].year == today.year:
        cutoff = date(today.year - 1, 12, 31)
        if payload["start_date"] >= cutoff:
            raise ValueError(
                "Disabling year-to-date data leaves no complete calendar year in the range"
            )
        payload["end_date"] = cutoff
        warnings.append(
            f"Excluded the incomplete {today.year} calendar year; end date moved to "
            f"{cutoff.isoformat()}"
        )
    return BacktestRequest.model_validate(payload), warnings
