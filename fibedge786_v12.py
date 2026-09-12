from flask import Flask, render_template_string, request
import pandas as pd, io, requests

app=Flask(__name__)
BASE='https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/'
SIG=BASE+'FIBEDGE_LATEST_SIGNALS.csv'
OPP=BASE+'FIBEDGE_BEST_OPPORTUNITIES_V3.csv'
MAP=BASE+'STOCK_UNIVERSE_MAPPING.csv'
FILTERS=[('ALL','All'),('NIFTY50','NIFTY 50'),('FNO','F&O'),('SMALLCAP250','Smallcap 250'),('MICROCAP250','Microcap 250')]
H={'User-Agent':'Mozilla/5.0','Cache-Control':'no-cache'}

HTML='''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FibEdge 786</title><style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial;background:linear-gradient(180deg,#06101d,#050c15);color:#eef5fd}.nav{position:sticky;top:0;z-index:99;background:#07111eee;border-bottom:1px solid #183049}.navin,.page{max-width:1450px;margin:auto}.navin{padding:13px 20px;display:flex;justify-content:space-between;align-items:center}.brand{font-weight:900;font-size:20px}.brand b{color:#25dc83}.page{padding:24px 20px 55px}h1{margin:0;font-size:clamp(28px,4vw,46px)}.sub{color:#7f95ad;font-size:12px;margin:8px 0 14px}.strategy{display:inline-flex;gap:8px;flex-wrap:wrap;background:#0c1a2a;border:1px solid #1f3851;border-radius:11px;padding:9px 11px;color:#9bb0c6;font-size:10px}.fresh{margin-top:18px;padding:12px 14px;border:1px solid #1d5c45;border-radius:12px;background:#0c211b80;font-size:11px;color:#8fa5bb}.fresh b{color:#27db84}.filters{position:sticky;top:62px;z-index:90;margin:16px 0 20px;padding:9px;border:1px solid #1e3852;border-radius:14px;background:#07111ef2}.chips{display:flex;gap:7px;overflow-x:auto;scrollbar-width:none}.chips::-webkit-scrollbar{display:none}.chip{white-space:nowrap;text-decoration:none;color:#91a7bd;background:#0c1c2d;border:1px solid #284159;padding:8px 12px;border-radius:999px;font-size:10px;font-weight:800}.chip.on{color:#04130b;background:#2cdd89;border-color:#2cdd89}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px}.stat{background:#0b1929;border:1px solid #1b324a;border-radius:14px;padding:15px}.lab{font-size:8px;color:#6c8198;text-transform:uppercase}.num{font-size:25px;font-weight:900;margin-top:5px}.g{color:#27dc84}.y{color:#f1c45c}.b{color:#62a8ff}.search{display:flex;gap:8px;background:#091725;border:1px solid #1b3148;border-radius:13px;padding:11px;margin-bottom:27px}.search input{flex:1;background:#06111d;border:1px solid #263d55;color:white;border-radius:9px;padding:11px}.search button,.load{border:0;border-radius:9px;background:#1a3047;color:#eef4fa;padding:10px 15px;font-weight:800;text-decoration:none;font-size:10px}.section{margin-bottom:32px}.head{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px;gap:10px}.title{font-size:19px;font-weight:900}.desc{color:#6f849b;font-size:10px;margin-top:3px}.count{font-size:9px;color:#9db0c5;border:1px solid #294159;border-radius:999px;padding:5px 8px}.quality{padding:16px;border:1px solid #29465f;border-radius:16px;background:#0a1929;margin-bottom:33px}.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:14px 0 17px}.sum{background:#081624;border:1px solid #203950;border-radius:10px;padding:11px}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}.card{background:#0b1a2b;border:1px solid #1d354d;border-radius:14px;overflow:hidden}.ctop{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:12px 13px;border-bottom:1px solid #193149}.sym{font-weight:900;font-size:16px}.badge{font-size:8px;font-weight:900;border-radius:999px;padding:5px 7px;background:#163047;color:#9eb2c8}.open{color:#27dc84;background:#123528}.near{color:#f1c45c;background:#392f16}.body{padding:13px}.price{font-size:23px;font-weight:900}.muted{font-size:9px;color:#687e96}.levels,.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.box{background:#091a2b;border-radius:8px;padding:8px}.box b{display:block;font-size:11px;margin-top:3px}table{width:100%;border-collapse:collapse;background:#091725;border:1px solid #1b324a;border-radius:13px;overflow:hidden}th,td{padding:11px;text-align:left;border-bottom:1px solid #152a3f;font-size:10px}th{font-size:8px;color:#6d829a;text-transform:uppercase;background:#0c1b2b}.empty{text-align:center;padding:22px;border:1px dashed #294159;border-radius:12px;color:#70859d;font-size:11px}.loadw{text-align:center;margin-top:14px}.foot{text-align:center;border-top:1px solid #172a3e;padding-top:22px;margin-top:40px;color:#587087;font-size:9px;line-height:1.7}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}.stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:700px){.navin{padding:11px 12px}.page{padding:17px 11px 36px}.filters{top:55px}.grid{grid-template-columns:1fr}.stats{gap:7px}.stat{padding:12px}.num{font-size:22px}.summary{grid-template-columns:1fr}.search{flex-direction:column}.levels{grid-template-columns:repeat(3,1fr)}table,thead,tbody,tr,th,td{display:block;width:100%}thead{display:none}tbody{display:grid;gap:9px}tr{display:grid;grid-template-columns:1fr 1fr;border:1px solid #1d354d;border-radius:12px;overflow:hidden;background:#0b1a2b}td{padding:9px 10px}td:before{content:attr(data-l);display:block;color:#647a91;font-size:7px;text-transform:uppercase;margin-bottom:2px}td:first-child{grid-column:1/-1;background:#0c1b2b;font-size:13px}.load{display:block;width:100%}}
</style></head><body><div class="nav"><div class="navin"><div class="brand">FibEdge <b>786</b></div><div class="muted">Auto-updated NSE Dashboard</div></div></div><div class="page"><h1>NSE Fibonacci Signal Dashboard</h1><div class="sub">Meaningful-swing signals with historical quality kept separate from current opportunity.</div><div class="strategy">8%+ decline • 15+ days • Entry 0.786 • SL 0.500 • Target 1.260</div><div class="fresh">Latest timestamp: <b>{{latest}}</b></div><div class="filters"><div class="chips">{% for k,l in filters %}<a class="chip {% if sel==k %}on{% endif %}" href="/?universe={{k}}">{{l}}</a>{% endfor %}</div></div><div class="stats"><div class="stat"><div class="lab">Stocks Scanned</div><div class="num">{{total}}</div></div><div class="stat"><div class="lab">Open Signals</div><div class="num g">{{open_n}}</div></div><div class="stat"><div class="lab">Near 0.786</div><div class="num y">{{near_n}}</div></div><div class="stat"><div class="lab">Waiting</div><div class="num b">{{wait_n}}</div></div></div><form class="search"><input type="hidden" name="universe" value="{{sel}}"><input name="q" value="{{q}}" placeholder="Search stock symbol..."><button>Search</button></form>
{% if q %}<div class="section"><div class="head"><div><div class="title">Search Results</div><div class="desc">{{q}}</div></div><div class="count">{{search_rows|length}}</div></div>{{ table(search_rows,'search')|safe }}</div>{% endif %}
<div class="quality" id="quality"><div class="title">🔥 Best Setups Now</div><div class="desc">5-year quality combined with current 0.786 position.</div><div class="summary"><div class="sum"><div class="lab">Strong Now</div><div class="num g">{{strong|length}}</div></div><div class="sum"><div class="lab">Good Setups</div><div class="num b">{{good_n}}</div></div><div class="sum"><div class="lab">Quality Watch</div><div class="num y">{{qwatch}}</div></div></div>{% if strong %}<div class="grid">{% for r in strong %}<div class="card"><div class="ctop"><div class="sym">{{r.Symbol}}</div><div class="badge open">STRONG NOW • {{r.Grade}} • {{r.Speed}}</div></div><div class="body"><div class="muted">Current Price</div><div class="price">₹{{r.Price}}</div><div class="muted">{{r.State}}</div><div class="metrics"><div class="box"><span class="lab">Entry</span><b>{{r.Entry}}</b></div><div class="box"><span class="lab">Win Rate</span><b>{{r.Win}}</b></div><div class="box"><span class="lab">Expectancy</span><b>{{r.Exp}}</b></div></div></div></div>{% endfor %}</div>{% else %}<div class="empty">No Strong Now setups.</div>{% endif %}</div>
<div class="section" id="open"><div class="head"><div><div class="title">Open Signals</div><div class="desc">Entry has already triggered.</div></div><div class="count">{{open_rows|length}}</div></div>{{ cards(open_rows,'OPEN')|safe }}{% if open_rows|length>ol %}<div class="loadw"><a class="load" href="/?universe={{sel}}&open_limit={{ol+24}}&watch_limit={{wl}}&quality_limit={{ql}}#open">Load More Open Signals</a></div>{% endif %}</div>
<div class="section"><div class="head"><div><div class="title">Near 0.786</div><div class="desc">Highest-priority upcoming setups.</div></div><div class="count">{{near_rows|length}}</div></div>{{ cards(near_rows,'NEAR ENTRY')|safe }}</div>
<div class="section" id="watch"><div class="head"><div><div class="title">Watchlist</div><div class="desc">Waiting setups within 10% of 0.786.</div></div><div class="count">{{watch_rows|length}}</div></div>{{ table(watch_rows[:wl],'watch')|safe }}{% if watch_rows|length>wl %}<div class="loadw"><a class="load" href="/?universe={{sel}}&open_limit={{ol}}&watch_limit={{wl+100}}&quality_limit={{ql}}#watch">Load More Watchlist Stocks</a></div>{% endif %}</div>
<div class="section" id="hist"><div class="head"><div><div class="title">📊 Good Historical Setups</div><div class="desc">Positive historical setups ranked by quality and speed.</div></div><div class="count">{{good_n}}</div></div>{{ table(good[:ql],'quality')|safe }}{% if good_n>ql %}<div class="loadw"><a class="load" href="/?universe={{sel}}&quality_limit={{ql+20}}&open_limit={{ol}}&watch_limit={{wl}}#hist">Load More Good Setups</a></div>{% endif %}</div><div class="foot">FibEdge 786 • Research use only • Market data may be delayed</div></div></body></html>'''

def get(url,t=15):
 r=requests.get(url,headers=H,timeout=t);r.raise_for_status();return r.text.lstrip('\ufeff')
def load(url): return pd.read_csv(io.StringIO(get(url)))
def norm(s): return s.astype(str).str.replace('.NS','',regex=False).str.strip().str.upper()
def mapping():
 try:
  m=load(MAP);m['SYMBOL']=m['SYMBOL'].astype(str).str.upper().str.strip();return m
 except: return pd.DataFrame()
def filt(df,key,m):
 if key=='ALL' or m.empty or df.empty:return df.copy()
 sy=set(m.loc[m[key].astype(str).str.upper().eq('YES'),'SYMBOL']);return df[norm(df['Symbol']).isin(sy)].copy()
def n(v):
 try:return f'{float(v):.2f}'
 except:return '-'
def rows(df):
 out=[]
 for _,r in df.iterrows():
  d=r.get('Distance %');out.append(dict(Symbol=str(r.get('Symbol','')).replace('.NS',''),Price=n(r.get('Price')),Status=str(r.get('Status','-')),Entry=n(r.get('Entry')),SL=n(r.get('SL')),Target=n(r.get('Target')),Distance=f'{float(d):.2f}%' if pd.notna(d) else '-',Time=str(r.get('Price Time','-'))))
 return out
def qrows(df):
 out=[]
 for _,r in df.iterrows():
  wr=r.get('Win Rate %');ex=r.get('Expectancy %');out.append(dict(Symbol=str(r.get('Symbol','')).replace('.NS',''),Price=n(r.get('Price')),Entry=n(r.get('Entry')),State=str(r.get('Current State','-')),Grade=str(r.get('Live Grade','-')),Speed=str(r.get('Speed Group','-')),Win=f'{float(wr):.2f}%' if pd.notna(wr) else '-',Exp=f'{float(ex):+.2f}%' if pd.notna(ex) else '-'))
 return out

def cards(rs,badge):
 if not rs:return '<div class="empty">No setups right now.</div>'
 x='<div class="grid">'
 for r in rs:x+=f'''<div class="card"><div class="ctop"><div class="sym">{r['Symbol']}</div><div class="badge {'open' if badge=='OPEN' else 'near'}">{badge}</div></div><div class="body"><div class="muted">Latest Price</div><div class="price">₹{r['Price']}</div><div class="muted">{r['Time']}</div><div class="levels"><div class="box"><span class="lab">Entry</span><b>{r['Entry']}</b></div><div class="box"><span class="lab">Stop</span><b>{r['SL']}</b></div><div class="box"><span class="lab">Target</span><b>{r['Target']}</b></div></div></div></div>'''
 return x+'</div>'
def table(rs,kind):
 if not rs:return '<div class="empty">No matching setups.</div>'
 if kind=='quality': cols=[('Symbol','Symbol'),('State','State'),('Price','Price'),('Entry','Entry'),('Grade','Grade'),('Win','Win Rate'),('Exp','Expectancy'),('Speed','Speed')]
 elif kind=='search': cols=[('Symbol','Symbol'),('Price','Price'),('Status','Status'),('Entry','Entry'),('SL','SL'),('Target','Target'),('Distance','Distance'),('Time','Price Time')]
 else: cols=[('Symbol','Symbol'),('Price','Price'),('Distance','Distance'),('Entry','Entry'),('SL','SL'),('Target','Target'),('Time','Price Time')]
 h='<table><thead><tr>'+''.join(f'<th>{b}</th>' for a,b in cols)+'</tr></thead><tbody>'
 for r in rs:h+='<tr>'+''.join(f'<td data-l="{b}">{r.get(a,"-")}</td>' for a,b in cols)+'</tr>'
 return h+'</tbody></table>'

@app.route('/')
def home():
 try: df,op=load(SIG),load(OPP)
 except Exception as e:return f'<body style="background:#07111f;color:white;padding:40px;font-family:Arial"><h2>FibEdge 786</h2><p>{e}</p></body>',503
 sel=request.args.get('universe','ALL').upper();valid={k for k,_ in FILTERS};sel=sel if sel in valid else 'ALL';m=mapping();df=filt(df,sel,m);op=filt(op,sel,m)
 od=df[df.Status.eq('OPEN')].copy();nd=df[df.Status.eq('NEAR 0.786')].copy();wd=df[df.Status.eq('WAITING FOR 0.786')].copy();ww=wd[wd['Distance %']<=10].copy()
 if not od.empty:od=od.sort_values('Distance %',key=lambda s:s.abs())
 if not nd.empty:nd=nd.sort_values('Distance %')
 if not ww.empty:ww=ww.sort_values('Distance %')
 strong=op[op.Opportunity.isin(['ELITE NOW','STRONG NOW'])].copy() if not op.empty else pd.DataFrame();good=op[op.Opportunity.eq('GOOD')].copy() if not op.empty else pd.DataFrame();qw=op[op.Opportunity.eq('WATCH')].copy() if not op.empty else pd.DataFrame()
 def lim(k,d):
  try:return max(d,int(request.args.get(k,d)))
  except:return d
 ql,ol,wl=lim('quality_limit',20),lim('open_limit',24),lim('watch_limit',100);q=request.args.get('q','').strip().upper();sd=df[norm(df.Symbol).str.contains(q,regex=False)].copy() if q else pd.DataFrame();vt=pd.to_datetime(df['Price Time'],errors='coerce').dropna();latest=vt.max().strftime('%d %b %Y • %I:%M %p') if len(vt) else 'Unavailable'
 return render_template_string(HTML,filters=FILTERS,sel=sel,total=len(df),open_n=len(od),near_n=len(nd),wait_n=len(wd),strong=qrows(strong),good=qrows(good),good_n=len(good),qwatch=len(qw),open_rows=rows(od),near_rows=rows(nd),watch_rows=rows(ww),search_rows=rows(sd),q=q,ql=ql,ol=ol,wl=wl,latest=latest,cards=cards,table=table)

if __name__=='__main__':app.run(host='0.0.0.0',port=5007,debug=True)
