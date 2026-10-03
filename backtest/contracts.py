"""Futures contract specifications and cost model.

Data symbols are index/commodity CFD proxies from histdata.com; we map each to the micro and mini
CME contract traded at Lucid Trading. P&L is computed per contract from point moves.
Commission: all-in round-trip per contract (exchange + clearing + NFA + platform), typical Tradovate/Rithmic
pricing at prop firms. Slippage: ticks per side applied to market and stop fills (not to limit fills).
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Contract:
    name: str          # e.g. MES
    data_symbol: str   # e.g. SPXUSD
    point_value: float # $ per 1.0 point move per contract
    tick: float        # minimum price increment
    commission_rt: float  # $ round trip per contract
    slip_ticks: float = 1.0  # per side, market/stop orders
    micro_ratio: int = 10    # micros per mini
    rth_open: str = '09:30'  # ET, primary session open used by RTH-only strategies
    rth_close: str = '16:00' # ET

CONTRACTS = {
    'MES': Contract('MES', 'SPXUSD', 5.0, 0.25, 1.30),
    'ES':  Contract('ES',  'SPXUSD', 50.0, 0.25, 4.20),
    'MNQ': Contract('MNQ', 'NSXUSD', 2.0, 0.25, 1.30),
    'NQ':  Contract('NQ',  'NSXUSD', 20.0, 0.25, 4.20),
    'MGC': Contract('MGC', 'XAUUSD', 10.0, 0.10, 1.30, rth_open='08:20', rth_close='13:30'),
    'GC':  Contract('GC',  'XAUUSD', 100.0, 0.10, 4.20, rth_open='08:20', rth_close='13:30'),
    'MCL': Contract('MCL', 'WTIUSD', 100.0, 0.01, 1.30, rth_open='09:00', rth_close='14:30'),
    'CL':  Contract('CL',  'WTIUSD', 1000.0, 0.01, 4.20, rth_open='09:00', rth_close='14:30'),
}

MICRO_OF = {'ES': 'MES', 'NQ': 'MNQ', 'GC': 'MGC', 'CL': 'MCL'}
