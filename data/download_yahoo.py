"""Download daily (2000+) and hourly (2y) futures data + VIX from Yahoo for basis checks and regime filters."""
import os, yfinance as yf, pandas as pd
ROOT = os.path.dirname(os.path.abspath(__file__)); PQ = os.path.join(ROOT, 'parquet'); os.makedirs(PQ, exist_ok=True)
def flat(d):
    if isinstance(d.columns, pd.MultiIndex): d.columns = [c[0].lower() for c in d.columns]
    else: d.columns = [c.lower() for c in d.columns]
    return d
for sym, name in [('ES=F','ES'),('NQ=F','NQ'),('GC=F','GC'),('CL=F','CL'),('^VIX','VIX'),('^GSPC','SPX'),('^NDX','NDX'),('MES=F','MES'),('MNQ=F','MNQ')]:
    d = flat(yf.download(sym, start='2000-01-01', interval='1d', progress=False, auto_adjust=False))
    d.index.name = 'date'; d.to_parquet(os.path.join(PQ, f'{name}_1d.parquet')); print(name, '1d', len(d))
for sym, name in [('ES=F','ES'),('NQ=F','NQ'),('GC=F','GC'),('CL=F','CL')]:
    d = flat(yf.download(sym, period='730d', interval='1h', progress=False, auto_adjust=False))
    d.index.name = 'ts'; d.to_parquet(os.path.join(PQ, f'{name}_1h.parquet')); print(name, '1h', len(d))
    d = flat(yf.download(sym, period='60d', interval='5m', progress=False, auto_adjust=False))
    d.index.name = 'ts'; d.to_parquet(os.path.join(PQ, f'{name}_5m.parquet')); print(name, '5m', len(d))
