# Portfolio Backtest API

FastAPI service responsible for market-data normalization, currency conversion, portfolio simulation, risk metrics, and optional factor/regime analysis.

The live data adapter is isolated behind `MarketDataProvider`; automated tests use deterministic synthetic histories and never depend on Yahoo availability.
