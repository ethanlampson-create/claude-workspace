"""Strategy registry. Each strategy module exposes:
  NAME, DESCRIPTION, CONTRACTS (list of default contracts), PARAMS (defaults dict), GRID (dict param -> list),
  generate(df1, contract, params) -> backtest.engine.Intents
A strategy id maps to the module strategies.<id> automatically (no registry edit needed); REGISTRY only holds aliases."""
import importlib

REGISTRY = {
    'orb': 'strategies.orb',
    'twap_revert': 'strategies.twap_revert',
    'intraday_momentum': 'strategies.intraday_momentum',
    'on_range_break': 'strategies.on_range_break',
}

def load(strategy_id):
    path = REGISTRY.get(strategy_id, f'strategies.{strategy_id}')
    return importlib.import_module(path)

def available():
    import os, glob
    here = os.path.dirname(os.path.abspath(__file__))
    return sorted(os.path.basename(p)[:-3] for p in glob.glob(os.path.join(here, '*.py')) if not os.path.basename(p).startswith('_') and os.path.basename(p) != 'common.py')
