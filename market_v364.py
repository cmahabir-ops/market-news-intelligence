"""Local Coinbase ticker research collector; no orders or credentials."""
import argparse, json, math, sqlite3, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PRODUCTS = ['BTC-USD','ETH-USD','SOL-USD','XRP-USD','ADA-USD','DOGE-USD']

def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db=sqlite3.connect(path, timeout=15)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS ticks (product TEXT, trade_id TEXT, ts REAL, received REAL, price REAL, size REAL, PRIMARY KEY(product,trade_id))')
    return db

def ingest(db, msg, received, diagnostics=None):
    def reject(reason):
        if diagnostics is not None: diagnostics[reason] += 1
        return False
    if msg.get('type')!='ticker' or msg.get('product_id') not in PRODUCTS: return False
    try:
        stamp=datetime.fromisoformat(msg['time'].replace('Z','+00:00'))
        if stamp.tzinfo is None: return reject("missing_timezone")
        ts=stamp.timestamp(); price=float(msg['price']); size=float(msg['last_size']); trade=str(msg['trade_id'])
        if not all(map(math.isfinite,[ts,price,size,received])) or price<=0 or size<0  : return reject("invalid_numeric")
        if ts>received+5:
            if diagnostics is not None: diagnostics["future_exchange_timestamp"] += 1
            return False
    except (KeyError,ValueError,TypeError,OverflowError): return reject("invalid_fields")
    return db.execute('INSERT OR IGNORE INTO ticks VALUES (?,?,?,?,?,?)',(msg['product_id'],trade,ts,received,price,size)).rowcount==1

def metrics(db, now):
    out=[]
    for product in PRODUCTS:
        rows=db.execute('SELECT ts,price,size FROM ticks WHERE product=? AND ts BETWEEN ? AND ? ORDER BY ts,trade_id',(product,now-300,now)).fetchall()
        if not rows: continue
        span=rows[-1][0]-rows[0][0]; age=now-rows[-1][0]
        # Observed span only; do not label partial windows as five-minute returns.
        returns=[math.log(b[1]/a[1]) for a,b in zip(rows,rows[1:])]
        out.append(dict(product=product,price=rows[-1][1],age_seconds=round(age,2),span_seconds=round(span,2),ticks=len(rows),observed_return_pct=round(100*(rows[-1][1]/rows[0][1]-1),4) if len(rows)>1 and span>0 else None,observed_realized_vol_pct=round(100*math.sqrt(sum(x*x for x in returns)),4) if len(rows)>1 and span>0 else None,observed_trade_size=sum(r[2] for r in rows)))
    return out

def main():
    import websocket
    p=argparse.ArgumentParser(); p.add_argument('--seconds',type=int,default=300); p.add_argument('--db',default='local_market/ticks.sqlite'); a=p.parse_args()
    if a.seconds<=0: p.error('seconds must be positive')
    db=connect(a.db); end=time.monotonic()+a.seconds; count=0; delay=1; messages=Counter(); stored=Counter(); rejected=Counter(); offsets={}; last_report=time.monotonic(); confirmed=set()
    try:
        while time.monotonic()<end:
            ws=None
            try:
                ws=websocket.create_connection('wss://ws-feed.exchange.coinbase.com',timeout=10)
                ws.send(json.dumps({'type':'subscribe','product_ids':PRODUCTS,'channels':['ticker','heartbeat']})); delay=1
                while time.monotonic()<end:
                    ws.settimeout(max(.1,min(10,end-time.monotonic())))
                    try: msg=json.loads(ws.recv())
                    except websocket.WebSocketTimeoutException:
                        print("Stream timeout; reconnecting",flush=True); break
                    if msg.get('type')=='error': raise RuntimeError(msg.get('message','subscription error'))
                    kind=msg.get('type'); product=msg.get('product_id','unknown'); received=time.time()
                    if kind=='subscriptions':
                        confirmed.update(x for c in msg.get('channels',[]) if c.get('name')=='ticker' for x in c.get('product_ids',[]))
                        print('Confirmed ticker subscriptions:',sorted(confirmed),flush=True)
                    if kind in ('ticker','heartbeat'):
                        messages[f'{kind}:{product}']+=1
                        try: offsets[product]=round(received-datetime.fromisoformat(msg['time'].replace('Z','+00:00')).timestamp(),3)
                        except (KeyError,ValueError,TypeError): pass
                    if kind=='ticker':
                        before=sum(rejected.values())
                        if ingest(db,msg,received,rejected):
                            count+=1; stored[product]+=1; db.commit()
                        elif sum(rejected.values())==before: rejected['duplicate_or_unknown_product']+=1
                    if time.monotonic()-last_report>=10:
                        print('Progress:',json.dumps(dict(stored=stored,rejected=rejected,receipt_minus_exchange_seconds=offsets)),flush=True); last_report=time.monotonic()
            except Exception as e:
                print('Connection issue:',type(e).__name__,str(e)[:200],flush=True); time.sleep(max(0,min(delay,end-time.monotonic()))); delay=min(delay*2,30)
            finally:
                if ws: ws.close()
    except KeyboardInterrupt: pass
    finally:
        print('Messages:',json.dumps(messages)); print('Stored by asset:',json.dumps(stored)); print('Rejected:',json.dumps(rejected)); print('Receipt minus exchange seconds:',json.dumps(offsets)); print('New stored ticks:',count); print(json.dumps(metrics(db,time.time()),indent=2)); db.close()
if __name__=='__main__': main()
