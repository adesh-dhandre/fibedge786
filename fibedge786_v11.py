from flask import Flask, render_template_string, request
import io
import json
from pathlib import Path

import pandas as pd
import requests

app = Flask(__name__)

BASE = "https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/"
SIGNALS_URL = BASE + "FIBEDGE_LATEST_SIGNALS.csv"
OPP_URL = BASE + "FIBEDGE_BEST_OPPORTUNITIES_V3.csv"
MAP_URL = BASE + "STOCK_UNIVERSE_MAPPING.csv"
PREMIUM_PLUS_URL = BASE + "netlify_site/premium_plus_candidates.json"

FILTERS = [
    ("ALL", "All"),
    ("NIFTY50", "NIFTY 50"),
    ("FNO", "F&O"),
    ("SMALLCAP250", "Smallcap 250"),
    ("MICROCAP250", "Microcap 250"),
]

MODES = {
    "CLASSIC": {
        "num": "01",
        "name": "Classic FibEdge",
        "rate": "30.44%",
        "rate_label": "Historical win rate",
        "summary": "Broadest 0.786 scanner for valid Fibonacci structures.",
    },
    "CLEAN": {
        "num": "02",
        "name": "Clean Swings",
        "rate": "42.52%",
        "rate_label": "Historical win rate",
        "summary": "Major high-to-low swings with cleaner recovery structure.",
    },
    "PREMIUM": {
        "num": "03",
        "name": "Premium Clean",
        "rate": "56.36%",
        "rate_label": "Resolved historical win rate",
        "summary": "Selective big-swing recovery tier.",
    },
    "PREMIUMPLUS": {
        "num": "04",
        "name": "Premium+ V1",
        "rate": "76.97%",
        "rate_label": "Historical win rate",
        "summary": "Rare behavior-confirmed setup after the daily candle closes.",
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Cache-Control": "no-cache",
}

def fetch_text(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text.lstrip("\ufeff")

def load_csv(url):
    return pd.read_csv(io.StringIO(fetch_text(url)))

def load_json(url):
    try:
        return json.loads(fetch_text(url))
    except Exception:
        return {"candidates": []}

def norm_symbol(value):
    return str(value or "").replace(".NS", "").strip().upper()

def safe_float(value):
    try:
        x = float(value)
        return x if pd.notna(x) else None
    except Exception:
        return None

def fmt_num(value, digits=2):
    x = safe_float(value)
    return f"{x:.{digits}f}" if x is not None else "-"

def fmt_pct(value, digits=2, plus=False):
    x = safe_float(value)
    if x is None:
        return "-"
    prefix = "+" if plus and x > 0 else ""
    return f"{prefix}{x:.{digits}f}%"

def days_between(a, b):
    try:
        x = pd.to_datetime(a, errors="coerce")
        y = pd.to_datetime(b, errors="coerce")
        if pd.isna(x) or pd.isna(y):
            return None
        return int((y - x).days)
    except Exception:
        return None

def load_mapping():
    local = Path("STOCK_UNIVERSE_MAPPING.csv")
    try:
        m = pd.read_csv(local) if local.exists() else load_csv(MAP_URL)
        if "SYMBOL" in m.columns:
            m["SYMBOL"] = m["SYMBOL"].astype(str).str.strip().str.upper()
        return m
    except Exception:
        return pd.DataFrame()

def apply_universe(df, universe, mapping, symbol_col="Symbol"):
    if df is None or df.empty or universe == "ALL":
        return df.copy()
    if mapping.empty or universe not in mapping.columns:
        return df.copy()
    allowed = set(
        mapping.loc[
            mapping[universe].astype(str).str.upper().eq("YES"),
            "SYMBOL"
        ]
    )
    out = df.copy()
    out["_SYMBOL"] = out[symbol_col].map(norm_symbol)
    out = out[out["_SYMBOL"].isin(allowed)].copy()
    out.drop(columns=["_SYMBOL"], inplace=True, errors="ignore")
    return out

def add_structure_metrics(df):
    out = df.copy()
    if out.empty:
        out["_decline"] = []
        out["_swing"] = []
        return out

    def decline(row):
        h = safe_float(row.get("High"))
        l = safe_float(row.get("Low"))
        if h is None or l is None or h <= 0:
            return None
        return (h - l) / h * 100

    out["_decline"] = out.apply(decline, axis=1)
    out["_swing"] = out.apply(
        lambda r: days_between(r.get("High Date"), r.get("Low Date")),
        axis=1,
    )
    return out

def make_quality_map(opp):
    if opp is None or opp.empty or "Symbol" not in opp.columns:
        return {}
    q = {}
    for _, row in opp.iterrows():
        symbol = norm_symbol(row.get("Symbol"))
        score = (
            safe_float(row.get("Opportunity Score V3"))
            or safe_float(row.get("Quality Score"))
            or 0.0
        )
        q[symbol] = {
            "score": score,
            "grade": str(row.get("Live Grade", row.get("Grade", "-"))),
            "opp": str(row.get("Opportunity", "-")),
        }
    return q

def row_to_card(row, quality=None, premium=False):
    symbol = norm_symbol(row.get("Symbol"))
    decline = row.get("_decline")
    swing = row.get("_swing")
    recovery = row.get("Recovery Efficiency", None)

    card = {
        "symbol": symbol,
        "price": fmt_num(row.get("Price")),
        "entry": fmt_num(row.get("Entry")),
        "stop": fmt_num(row.get("SL")),
        "target": fmt_num(row.get("Target")),
        "distance": fmt_pct(row.get("Distance %")),
        "decline": f"{float(decline):.1f}%" if decline is not None and pd.notna(decline) else "-",
        "swing": f"{int(swing)}d" if swing is not None and pd.notna(swing) else "-",
        "status": str(row.get("Status", "-")),
        "quality": quality or {},
        "recovery": fmt_num(recovery) if premium and recovery is not None and pd.notna(recovery) else None,
    }
    return card

def cards_from_df(df, quality_map=None, premium=False):
    quality_map = quality_map or {}
    return [
        row_to_card(row, quality_map.get(norm_symbol(row.get("Symbol"))), premium=premium)
        for _, row in df.iterrows()
    ]

def abs_distance_sort(df):
    if df.empty:
        return df
    out = df.copy()
    out["_absdist"] = pd.to_numeric(out.get("Distance %"), errors="coerce").abs()
    out = out.sort_values("_absdist", na_position="last")
    return out.drop(columns=["_absdist"], errors="ignore")

def distance_sort(df):
    if df.empty:
        return df
    out = df.copy()
    out["_dist"] = pd.to_numeric(out.get("Distance %"), errors="coerce")
    out = out.sort_values("_dist", na_position="last")
    return out.drop(columns=["_dist"], errors="ignore")

def build_classic(signals, opp):
    s = add_structure_metrics(signals)
    current = s[s["Status"].isin(["OPEN", "ENTRY AREA", "NEAR 0.786"])].copy()

    open_df = abs_distance_sort(current[current["Status"].isin(["OPEN", "ENTRY AREA"])].copy())
    near_df = distance_sort(current[current["Status"].eq("NEAR 0.786")].copy())

    qmap = make_quality_map(opp)
    best = current.copy()
    if not best.empty:
        best["_quality"] = best["Symbol"].map(
            lambda v: qmap.get(norm_symbol(v), {}).get("score", 0.0)
        )
        best["_absdist"] = pd.to_numeric(best.get("Distance %"), errors="coerce").abs()
        best = best.sort_values(
            ["_quality", "_absdist"],
            ascending=[False, True],
            na_position="last",
        ).drop(columns=["_quality", "_absdist"], errors="ignore").head(9)

    return {
        "best": cards_from_df(best, qmap),
        "open": cards_from_df(open_df, qmap),
        "near": cards_from_df(near_df, qmap),
        "note": "Broad live 0.786 structures. Best Setups prioritizes current quality and distance.",
    }

def build_clean(signals, opp, premium=False):
    s = add_structure_metrics(signals)
    current = s[s["Status"].isin(["OPEN", "ENTRY AREA", "NEAR 0.786"])].copy()

    clean = current[
        pd.to_numeric(current["_decline"], errors="coerce").ge(20)
        & pd.to_numeric(current["_swing"], errors="coerce").ge(40)
    ].copy()

    qmap = make_quality_map(opp)

    open_df = abs_distance_sort(clean[clean["Status"].isin(["OPEN", "ENTRY AREA"])].copy())
    near_df = distance_sort(clean[clean["Status"].eq("NEAR 0.786")].copy())

    best = clean.copy()
    if not best.empty:
        best["_quality"] = best["Symbol"].map(
            lambda v: qmap.get(norm_symbol(v), {}).get("score", 0.0)
        )
        best["_absdist"] = pd.to_numeric(best.get("Distance %"), errors="coerce").abs()
        if premium:
            best = best.sort_values(
                ["_quality", "_absdist"],
                ascending=[False, True],
                na_position="last",
            )
        else:
            best = best.sort_values(
                ["_absdist", "_quality"],
                ascending=[True, False],
                na_position="last",
            )
        best = best.drop(columns=["_quality", "_absdist"], errors="ignore").head(9)

    note = (
        "Current clean-swing candidates filtered to 20%+ decline and 40+ swing days."
        if not premium
        else "Premium Clean historical result is 56.36% resolved. Live cards use the current structured candidate feed; Recovery Efficiency is shown only when that field is present."
    )

    return {
        "best": cards_from_df(best, qmap, premium=premium),
        "open": cards_from_df(open_df, qmap, premium=premium),
        "near": cards_from_df(near_df, qmap, premium=premium),
        "note": note,
    }

def build_premium_plus(payload, universe, mapping):
    rows = payload.get("candidates", []) if isinstance(payload, dict) else []
    allowed = None
    if universe != "ALL" and not mapping.empty and universe in mapping.columns:
        allowed = set(
            mapping.loc[
                mapping[universe].astype(str).str.upper().eq("YES"),
                "SYMBOL"
            ]
        )

    cards = []
    for row in rows:
        symbol = norm_symbol(row.get("symbol"))
        if allowed is not None and symbol not in allowed:
            continue
        cards.append({
            "symbol": symbol,
            "price": fmt_num(row.get("close")),
            "entry": fmt_num(row.get("fib_0786")),
            "stop": fmt_num(row.get("sl")),
            "target": fmt_num(row.get("target")),
            "distance": "-",
            "decline": fmt_pct(row.get("decline_pct")),
            "swing": f"{row.get('swing_days', '-')}d",
            "status": "CONFIRMED",
            "lower_wick": fmt_pct(row.get("lower_wick_pct")),
            "compression": fmt_num(row.get("compression_3v10")),
            "close_above": fmt_pct(row.get("close_vs_786_pct"), plus=True),
        })

    return {
        "best": cards,
        "open": [],
        "near": [],
        "note": "Frozen V1 behavior confirmation. Candidates appear only after a completed daily candle.",
    }

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="600">
<title>FibEdge 786</title>
<style>
*{box-sizing:border-box}
:root{
  --bg:#06101b;
  --panel:#0a1928;
  --panel2:#0d1f31;
  --border:#1c3a54;
  --blue:#58bfff;
  --blue2:#88d2ff;
  --green:#4ce0a5;
  --gold:#e9bd58;
  --text:#eef7ff;
  --muted:#7891aa;
}
body{
  margin:0;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
  background:
    radial-gradient(circle at 82% 0%,rgba(61,132,205,.09),transparent 28%),
    linear-gradient(180deg,#071320,#050c15);
  color:var(--text);
}
a{text-decoration:none;color:inherit}
.nav{
  position:sticky;top:0;z-index:100;
  background:rgba(5,15,26,.96);
  border-bottom:1px solid #17324a;
  backdrop-filter:blur(14px);
}
.navin,.page{max-width:1450px;margin:auto}
.navin{padding:15px 22px;display:flex;justify-content:space-between;align-items:center}
.brand{display:flex;align-items:center;gap:10px;font-size:21px;font-weight:900}
.brandmark{
  width:35px;height:35px;border-radius:10px;display:grid;place-items:center;
  background:#123c32;border:1px solid #266f5b;color:#63e8b0
}
.brand b{color:#43bfff}
.navmeta{text-align:right;color:#7189a0;font-size:10px;line-height:1.45}
.navmeta strong{color:#69e4b8}
.page{padding:26px 22px 55px}
.guide{
  padding:18px;
  background:#081725;
  border:1px solid #193850;
  border-radius:16px;
  margin-bottom:18px;
}
.guide-title{font-size:15px;font-weight:900;margin-bottom:12px}
.guide-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}
.guide-item{padding:11px 12px;background:#091b2b;border:1px solid #173650;border-radius:10px}
.guide-item b{font-size:10px}.guide-item b span{color:var(--blue);margin-right:4px}
.guide-item p{margin:5px 0 0;color:var(--muted);font-size:8px;line-height:1.45}
.guide-item.gold{border-color:rgba(233,189,88,.38)}.guide-item.gold b span{color:var(--gold)}
.status-guide{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px}
.status-guide span{font-size:8px;color:#7891aa;padding:6px 9px;border:1px solid #18364f;border-radius:999px;background:#071521}
.status-guide b{color:#dfefff}
.modes{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:12px;
  padding:9px;
  border:1px solid #19384f;
  border-radius:16px;
  background:#071521;
  margin-bottom:18px;
}
.mode{
  min-height:130px;
  padding:17px;
  border:1px solid #21415d;
  border-radius:13px;
  background:linear-gradient(145deg,#0e2235,#091725);
  transition:.16s ease;
}
.mode:hover{transform:translateY(-2px);border-color:#3f8fca}
.mode.on{border-color:#56bfff;background:linear-gradient(145deg,#113252,#0a1d2f)}
.mode.gold{border-color:rgba(233,189,88,.42)}
.mode.gold.on{border-color:var(--gold);background:linear-gradient(145deg,#282317,#101b27)}
.mode .num{font-size:9px;font-weight:900;color:var(--blue)}
.mode.gold .num,.mode.gold .rate{color:var(--gold)}
.mode .name{display:block;font-size:15px;font-weight:850;margin-top:6px}
.mode .rate{display:block;font-size:27px;font-weight:900;color:var(--blue);margin-top:13px}
.mode .rate-label{display:block;font-size:7px;color:#6f899f;text-transform:uppercase;letter-spacing:.08em;margin-top:4px}
.filters{display:flex;gap:7px;flex-wrap:wrap;padding:9px;background:#081726;border:1px solid #193750;border-radius:14px;margin-bottom:18px}
.chip{padding:8px 12px;border-radius:999px;background:#0c1d2e;border:1px solid #24435d;color:#90a8bd;font-size:9px;font-weight:800}
.chip.on{background:#1782c1;border-color:#48baff;color:#fff}
.fresh{
  display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap;
  padding:11px 13px;border:1px solid #1b3a54;border-radius:12px;
  background:#081726;color:#8da3b7;font-size:9px;margin-bottom:18px
}
.fresh b{color:#68ddba}
.mode-summary{
  display:flex;justify-content:space-between;align-items:flex-start;gap:15px;
  padding:16px 18px;background:#081726;border:1px solid #1b3a54;border-radius:14px;margin-bottom:20px
}
.mode-summary h2{margin:0;font-size:22px}.mode-summary p{margin:5px 0 0;color:#7891aa;font-size:9px;line-height:1.5}
.mode-pill{font-size:8px;font-weight:900;padding:7px 10px;border:1px solid #28506d;border-radius:999px;color:#85cbf6;white-space:nowrap}
.mode-pill.gold{border-color:rgba(233,189,88,.45);color:var(--gold)}
.section{
  margin-bottom:24px;
  padding:16px;
  background:#081726;
  border:1px solid #1a3952;
  border-radius:15px
}
.section.best{border-top:2px solid #53b8f1}
.section.open{border-top:2px solid #43daa2}
.section.near{border-top:2px solid #e3b656}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:12px;margin-bottom:13px}
.section-title{font-size:19px;font-weight:900}
.section-desc{font-size:9px;color:#748da3;margin-top:4px}
.count{font-size:8px;color:#a8bdd0;padding:5px 8px;border:1px solid #29465f;border-radius:999px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}
.card{
  background:linear-gradient(150deg,#0d2032,#091624);
  border:1px solid #1d3d59;
  border-radius:13px;
  overflow:hidden;
  transition:.16s ease
}
.card:hover{transform:translateY(-2px);border-color:#3d92cb}
.card-top{display:flex;justify-content:space-between;gap:10px;padding:14px;border-bottom:1px solid #183650}
.symbol{font-size:16px;font-weight:900}
.badge{font-size:7px;color:#57bdf4;text-transform:uppercase;letter-spacing:.08em;margin-top:3px;font-weight:850}
.badge.gold{color:var(--gold)}
.price{font-size:20px;font-weight:900;white-space:nowrap}
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;padding:13px}
.metric{background:#071522;border:1px solid #18344c;border-radius:8px;padding:8px}
.metric span{display:block;color:#6f899f;font-size:7px;text-transform:uppercase;letter-spacing:.05em}
.metric b{display:block;color:#dcecff;font-size:10px;margin-top:4px}
.metric.special{border-color:rgba(88,191,255,.34)}
.metric.gold{border-color:rgba(233,189,88,.38)}
.empty{text-align:center;padding:28px 16px;border:1px dashed #29475f;border-radius:11px;color:#748da4;font-size:10px;line-height:1.55}
.foot{text-align:center;margin-top:35px;padding-top:20px;border-top:1px solid #173048;color:#587188;font-size:8px}
.error{padding:16px;border:1px solid #704348;background:#2a171c;border-radius:12px;color:#ffc6cb;font-size:10px}
@media(max-width:980px){.modes,.guide-grid{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:620px){
  .navin,.page{padding-left:12px;padding-right:12px}
  .modes{grid-template-columns:1fr 1fr;gap:8px}
  .mode{min-height:115px;padding:13px}
  .mode .rate{font-size:23px}
  .guide-grid,.grid{grid-template-columns:1fr}
  .metrics{grid-template-columns:repeat(2,1fr)}
  .mode-summary{flex-direction:column}
}
</style>
</head>
<body>
<div class="nav">
  <div class="navin">
    <div class="brand"><div class="brandmark">F</div><span>FibEdge <b>786</b></span></div>
    <div class="navmeta">NSE setup intelligence<br><strong>Server-rendered live dashboard</strong></div>
  </div>
</div>

<main class="page">

  <section class="guide">
    <div class="guide-title">How to read FibEdge</div>
    <div class="guide-grid">
      {% for key, item in modes.items() %}
      <div class="guide-item {% if key=='PREMIUMPLUS' %}gold{% endif %}">
        <b><span>{{ item.num }}</span> {{ item.name }}</b>
        <p>{{ item.summary }}</p>
      </div>
      {% endfor %}
    </div>
    <div class="status-guide">
      <span><b>Best Setups</b> highest-priority stocks</span>
      <span><b>Open Now</b> entry already triggered</span>
      <span><b>Near Structure</b> approaching 0.786</span>
    </div>
  </section>

  <section class="modes">
    {% for key, item in modes.items() %}
    <a class="mode {% if mode==key %}on{% endif %} {% if key=='PREMIUMPLUS' %}gold{% endif %}"
       href="/?mode={{ key }}&universe={{ universe }}">
      <span class="num">{{ item.num }}</span>
      <span class="name">{{ item.name }}</span>
      <span class="rate">{{ item.rate }}</span>
      <span class="rate-label">{{ item.rate_label }}</span>
    </a>
    {% endfor %}
  </section>

  <div class="filters">
    {% for key, label in filters %}
      <a class="chip {% if universe==key %}on{% endif %}"
         href="/?mode={{ mode }}&universe={{ key }}">{{ label }}</a>
    {% endfor %}
  </div>

  <div class="fresh">
    <span>Latest timestamp: <b>{{ latest }}</b></span>
    <span>Universe: <b>{{ universe_label }}</b></span>
  </div>

  <section class="mode-summary">
    <div>
      <h2>{{ modes[mode].name }}</h2>
      <p>{{ data.note }}</p>
    </div>
    <div class="mode-pill {% if mode=='PREMIUMPLUS' %}gold{% endif %}">
      {{ modes[mode].rate }} HISTORICAL
    </div>
  </section>

  {% macro card(c, premium_plus=False) -%}
  <div class="card">
    <div class="card-top">
      <div>
        <div class="symbol">{{ c.symbol }}</div>
        <div class="badge {% if premium_plus %}gold{% endif %}">{{ c.status }}</div>
      </div>
      <div class="price">₹{{ c.price }}</div>
    </div>
    <div class="metrics">
      <div class="metric"><span>Entry</span><b>₹{{ c.entry }}</b></div>
      <div class="metric"><span>Stop</span><b>₹{{ c.stop }}</b></div>
      <div class="metric"><span>Target</span><b>₹{{ c.target }}</b></div>
      <div class="metric"><span>Distance</span><b>{{ c.distance }}</b></div>
      <div class="metric"><span>Decline</span><b>{{ c.decline }}</b></div>
      <div class="metric"><span>Swing</span><b>{{ c.swing }}</b></div>

      {% if c.recovery %}
      <div class="metric special"><span>Recovery Eff.</span><b>{{ c.recovery }}</b></div>
      {% endif %}

      {% if premium_plus %}
      <div class="metric gold"><span>Lower Wick</span><b>{{ c.lower_wick }}</b></div>
      <div class="metric gold"><span>Compression</span><b>{{ c.compression }}</b></div>
      <div class="metric gold"><span>Close above 0.786</span><b>{{ c.close_above }}</b></div>
      {% endif %}
    </div>
  </div>
  {%- endmacro %}

  <section class="section best">
    <div class="section-head">
      <div><div class="section-title">Best Setups</div><div class="section-desc">Highest-priority stocks from the selected strategy.</div></div>
      <div class="count">{{ data.best|length }}</div>
    </div>
    {% if data.best %}
      <div class="grid">
      {% for c in data.best %}
        {{ card(c, mode=='PREMIUMPLUS') }}
      {% endfor %}
      </div>
    {% else %}
      <div class="empty">
        {% if mode=='PREMIUMPLUS' %}
          <b>No Premium+ setup today.</b><br>Waiting for the frozen V1 conditions after a completed daily candle.
        {% else %}
          No current setup in this strategy and universe.
        {% endif %}
      </div>
    {% endif %}
  </section>

  <section class="section open">
    <div class="section-head">
      <div><div class="section-title">Open Now</div><div class="section-desc">Entry condition has triggered.</div></div>
      <div class="count">{{ data.open|length }}</div>
    </div>
    {% if data.open %}
      <div class="grid">
      {% for c in data.open %}
        {{ card(c, mode=='PREMIUMPLUS') }}
      {% endfor %}
      </div>
    {% else %}
      <div class="empty">No open setup right now.</div>
    {% endif %}
  </section>

  <section class="section near">
    <div class="section-head">
      <div><div class="section-title">Near Structure</div><div class="section-desc">Approaching the 0.786 entry structure.</div></div>
      <div class="count">{{ data.near|length }}</div>
    </div>
    {% if data.near %}
      <div class="grid">
      {% for c in data.near %}
        {{ card(c, mode=='PREMIUMPLUS') }}
      {% endfor %}
      </div>
    {% else %}
      <div class="empty">No near-structure setup right now.</div>
    {% endif %}
  </section>

  <div class="foot">FibEdge 786 • Research use only • Historical results are not future guarantees • Market data may be delayed</div>
</main>
</body>
</html>"""

@app.route("/")
def home():
    mode = request.args.get("mode", "CLASSIC").upper()
    if mode not in MODES:
        mode = "CLASSIC"

    universe = request.args.get("universe", "ALL").upper()
    valid_universes = {k for k, _ in FILTERS}
    if universe not in valid_universes:
        universe = "ALL"

    try:
        signals = load_csv(SIGNALS_URL)
        opp = load_csv(OPP_URL)
        mapping = load_mapping()

        signals = apply_universe(signals, universe, mapping)
        opp = apply_universe(opp, universe, mapping)

        if mode == "CLASSIC":
            data = build_classic(signals, opp)
        elif mode == "CLEAN":
            data = build_clean(signals, opp, premium=False)
        elif mode == "PREMIUM":
            data = build_clean(signals, opp, premium=True)
        else:
            data = build_premium_plus(load_json(PREMIUM_PLUS_URL), universe, mapping)

        valid_times = pd.to_datetime(signals.get("Price Time"), errors="coerce").dropna()
        latest = (
            valid_times.max().strftime("%d %b %Y • %I:%M %p")
            if len(valid_times)
            else "Unavailable"
        )

        universe_label = dict(FILTERS).get(universe, "All")

        return render_template_string(
            HTML,
            modes=MODES,
            mode=mode,
            filters=FILTERS,
            universe=universe,
            universe_label=universe_label,
            latest=latest,
            data=data,
        )

    except Exception as exc:
        return render_template_string(
            """<!doctype html><html><body style="margin:0;background:#07111d;color:#fff;font-family:Arial;padding:40px">
            <h2>FibEdge 786</h2>
            <div style="max-width:760px;padding:18px;border:1px solid #704348;border-radius:12px;background:#29171c">
              <b>Dashboard data could not be loaded.</b>
              <p style="color:#ffc6cb">{{ error }}</p>
            </div>
            </body></html>""",
            error=str(exc),
        ), 503

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5007, debug=True)
