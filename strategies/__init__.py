"""Strategy registry. Each strategy module exposes:
  NAME, DESCRIPTION, CONTRACTS (list of default contracts), PARAMS (defaults dict), GRID (dict param -> list),
  generate(df1, contract, params) -> backtest.engine.Intents
Register by adding to REGISTRY (id -> module path)."""
import importlib

REGISTRY = {
    'orb': 'strategies.orb',
    'twap_revert': 'strategies.twap_revert',
    'intraday_momentum': 'strategies.intraday_momentum',
    'on_range_break': 'strategies.on_range_break',
}

def load(strategy_id):
    return importlib.import_module(REGISTRY[strategy_id])
