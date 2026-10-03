"""Download free 1-minute bar data from histdata.com for index/commodity CFD proxies.

Timestamps are US Eastern time with DST (verified empirically, see download_symbol); localised to America/New_York.
Volume column is always 0 on histdata (no volume available).
Usage: python3 data/download_histdata.py [SYMBOL ...]
"""
import re, io, os, sys, time, zipfile, datetime as dt
import requests, pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw'); PQ = os.path.join(ROOT, 'parquet')
os.makedirs(RAW, exist_ok=True); os.makedirs(PQ, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
START_YEAR = {'SPXUSD': 2010, 'NSXUSD': 2010, 'XAUUSD': 2009, 'WTIUSD': 2010, 'BCOUSD': 2010, 'EURUSD': 2009}

def fetch(session, pair, year, month=None):
    base = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair.lower()}/{year}"
    url = base + (f"/{month}" if month else "")
    r = session.get(url, timeout=90); r.raise_for_status()
    m = re.search(r'id="tk" value="([^"]+)"', r.text)
    if not m:
        return None
    data = {'tk': m.group(1), 'date': str(year), 'datemonth': f"{year}{month:02d}" if month else str(year),
            'platform': 'ASCII', 'timeframe': 'M1', 'fxpair': pair.upper()}
    r2 = session.post('https://www.histdata.com/get.php', data=data, headers={'Referer': url}, timeout=300)
    if r2.content[:2] != b'PK':
        return None
    return r2.content

def parse_zip(content):
    z = zipfile.ZipFile(io.BytesIO(content))
    name = [n for n in z.namelist() if n.endswith('.csv')][0]
    df = pd.read_csv(z.open(name), sep=';', header=None, names=['ts', 'open', 'high', 'low', 'close', 'vol'])
    df['ts'] = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S')
    return df

def download_symbol(pair, today):
    s = requests.Session(); s.headers.update(UA)
    frames = []
    y0 = START_YEAR.get(pair.upper(), 2010)
    for year in range(y0, today.year + 1):
        if year < today.year:
            cache = os.path.join(RAW, f"{pair}_{year}.zip")
            if os.path.exists(cache):
                content = open(cache, 'rb').read()
            else:
                content = None
                for attempt in range(4):
                    try:
                        content = fetch(s, pair, year); break
                    except Exception as e:
                        print(pair, year, 'retry', attempt, e, flush=True); time.sleep(2 ** attempt)
                if content is None:
                    print(pair, year, 'NOT AVAILABLE', flush=True); continue
                open(cache, 'wb').write(content)
            df = parse_zip(content); frames.append(df); print(pair, year, len(df), flush=True)
        else:
            for month in range(1, today.month + 1):
                cache = os.path.join(RAW, f"{pair}_{year}{month:02d}.zip")
                if os.path.exists(cache):
                    content = open(cache, 'rb').read()
                else:
                    content = None
                    for attempt in range(4):
                        try:
                            content = fetch(s, pair, year, month); break
                        except Exception as e:
                            print(pair, year, month, 'retry', attempt, e, flush=True); time.sleep(2 ** attempt)
                    if content is None:
                        print(pair, year, month, 'NOT AVAILABLE', flush=True); continue
                    open(cache, 'wb').write(content)
                df = parse_zip(content); frames.append(df); print(pair, year, month, len(df), flush=True)
    if not frames:
        print(pair, 'NO DATA'); return
    df = pd.concat(frames).drop_duplicates('ts').sort_values('ts').reset_index(drop=True)
    # histdata documents its stamps as EST without DST, but for these index/metal files the stamps empirically follow
    # US Eastern time WITH DST for every year (Sunday Globex open is stamped 18:00 in summer and winter, and the
    # 09:30 ET cash-open bar is the widest bar in both seasons). Localise directly; DST transition hours fall on
    # Sunday 02:00 when the market is closed, so no bars are lost.
    df['ts'] = df['ts'].dt.tz_localize('America/New_York', ambiguous='NaT', nonexistent='NaT')
    df = df.dropna(subset=['ts'])
    df = df.drop(columns=['vol'])
    out = os.path.join(PQ, f"{pair.upper()}_1m.parquet")
    df.to_parquet(out, index=False)
    print(pair, 'SAVED', out, len(df), df['ts'].min(), df['ts'].max(), flush=True)

if __name__ == '__main__':
    today = dt.date.today()
    # Only completed months are available for the current year.
    today = today.replace(day=1) - dt.timedelta(days=1)
    syms = sys.argv[1:] or ['SPXUSD', 'NSXUSD', 'XAUUSD', 'WTIUSD']
    for p in syms:
        download_symbol(p, today)
