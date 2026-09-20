from flask import Flask, render_template_string, request
import pandas as pd
import io
import requests
from pathlib import Path

app = Flask(__name__)

GITHUB_OPPORTUNITY_URL = (
    "https://raw.githubusercontent.com/"
    "adesh-dhandre/fibedge786/master/"
    "FIBEDGE_BEST_OPPORTUNITIES_V3.csv"
)

GITHUB_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "adesh-dhandre/fibedge786/master/"
    "FIBEDGE_LATEST_SIGNALS.csv"
)

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#07111f">
<title>FibEdge 786 — Dashboard V2 Preview</title>
<style>
*{box-sizing:border-box}
:root{
  --accent:#2ee59d;--accent2:#8af7c8;--accent-rgb:46,229,157;
  --bg:#050b13;--bg2:#08111d;--panel:#0b1724;--panel2:#0f1d2c;
  --border:#203349;--border2:#29445e;--text:#f5f8fc;--muted:#95a8ba;
  --danger:#ff6e86;--warning:#f7c65b;--blue:#67a7ff
}
body.theme-all{--accent:#2ee59d;--accent2:#8af7c8;--accent-rgb:46,229,157}
body.theme-nifty50{--accent:#5396ff;--accent2:#9fc5ff;--accent-rgb:83,150,255}
body.theme-fno{--accent:#ae78ff;--accent2:#d1afff;--accent-rgb:174,120,255}
body.theme-nifty500{--accent:#45c7ff;--accent2:#9fe5ff;--accent-rgb:69,199,255}
body.theme-midsmall400{--accent:#27d7c6;--accent2:#8cf4ea;--accent-rgb:39,215,198}
body.theme-smallcap250{--accent:#f5ad4a;--accent2:#ffd18a;--accent-rgb:245,173,74}
body.theme-microcap250{--accent:#ff6f9f;--accent2:#ffacc8;--accent-rgb:255,111,159}
html{scroll-behavior:smooth}
body{
  --mode-accent:#2ee59d;--mode-accent2:#8af7c8;--mode-rgb:46,229,157;
  margin:0;color:var(--text);min-height:100vh;
  font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
  background:
    radial-gradient(circle at 8% 0%,rgba(var(--mode-rgb),.16),transparent 26%),
    radial-gradient(circle at 92% 8%,rgba(83,150,255,.08),transparent 20%),
    linear-gradient(180deg,#07111f 0%,#050b13 56%,#03080e 100%);
  transition:background .35s ease
}
body.mode-clean{--mode-accent:#52b7ff;--mode-accent2:#80e7ff;--mode-rgb:82,183,255}
body.mode-premium{--mode-accent:#f4c55c;--mode-accent2:#ff8ad8;--mode-rgb:244,197,92}
body:after{
  content:"";position:fixed;inset:auto -12vw -28vh auto;width:52vw;height:52vw;z-index:-2;
  border-radius:50%;background:radial-gradient(circle,rgba(var(--mode-rgb),.12),transparent 63%);
  filter:blur(20px);animation:orbFloat 12s ease-in-out infinite alternate;pointer-events:none
}
body:before{
  content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.16;
  background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
  background-size:44px 44px
}
button,input{font:inherit}
button{color:inherit}
.nav{
  position:sticky;top:0;z-index:100;
  background:rgba(5,13,23,.91);backdrop-filter:blur(18px);
  border-bottom:1px solid rgba(var(--accent-rgb),.24);
  box-shadow:0 10px 35px rgba(0,0,0,.24)
}
.navin,.page{max-width:1480px;margin:auto}
.navin{padding:15px 22px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.brand{display:flex;align-items:center;gap:11px;font-size:22px;font-weight:950;letter-spacing:-.035em}
.brandmark{
  width:35px;height:35px;border-radius:11px;display:grid;place-items:center;
  background:linear-gradient(135deg,rgba(var(--accent-rgb),.35),rgba(var(--accent-rgb),.07));
  border:1px solid rgba(var(--accent-rgb),.55);color:var(--accent2);font-weight:950;
  box-shadow:0 0 24px rgba(var(--accent-rgb),.15)
}
.brand b{color:var(--accent)}
.navmeta{text-align:right;font-size:11px;line-height:1.45;color:var(--muted)}
.navmeta strong{color:var(--accent2)}
.page{padding:29px 22px 60px}
.hero{
  position:relative;overflow:hidden;padding:28px 28px 25px;
  background:linear-gradient(135deg,rgba(var(--mode-rgb),.13),rgba(11,23,36,.84) 46%,rgba(7,14,24,.98));
  border:1px solid rgba(var(--mode-rgb),.32);border-radius:24px;
  box-shadow:0 24px 70px rgba(0,0,0,.28),0 0 0 1px rgba(255,255,255,.018) inset;
  animation:heroIn .7s cubic-bezier(.2,.8,.2,1) both
}
.hero:before{
  content:"";position:absolute;left:-22%;top:-160%;width:55%;height:420%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.035),transparent);
  transform:rotate(18deg);animation:heroSweep 7s linear infinite;pointer-events:none
}
.hero:after{
  content:"786";position:absolute;right:22px;top:-18px;font-size:130px;font-weight:950;
  letter-spacing:-.08em;color:rgba(var(--accent-rgb),.055);pointer-events:none
}
.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:.16em;color:var(--mode-accent2);font-weight:900;text-shadow:0 0 18px rgba(var(--mode-rgb),.22)}
h1{font-size:clamp(34px,5vw,58px);letter-spacing:-.05em;line-height:.98;margin:9px 0 12px}
.hero p{max-width:800px;margin:0;color:#a1b3c5;font-size:14px;line-height:1.65}
.herofoot{display:flex;flex-wrap:wrap;gap:9px;margin-top:19px}
.tag{padding:8px 11px;border-radius:999px;font-size:10px;font-weight:850;color:#b7c8d8;background:#0b1a29;border:1px solid #274057}
.tag.live{color:var(--accent2);border-color:rgba(var(--accent-rgb),.38);background:rgba(var(--accent-rgb),.07)}
.modebar{
  margin:18px 0 12px;padding:8px;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;
  background:rgba(7,15,25,.9);border:1px solid #20344a;border-radius:17px
}
.mode{
  position:relative;overflow:hidden;border:1px solid transparent;background:transparent;border-radius:13px;padding:15px 14px;cursor:pointer;
  text-align:left;transition:.22s ease;min-width:0
}
.mode:hover{background:#0d1b2a}
.mode.on{
  background:linear-gradient(135deg,rgba(var(--mode-rgb),.20),rgba(var(--mode-rgb),.055));
  border-color:rgba(var(--mode-rgb),.5);box-shadow:0 12px 34px rgba(var(--mode-rgb),.11)
}
.mode.on:after{
  content:"";position:absolute;left:-30%;bottom:0;width:32%;height:2px;
  background:linear-gradient(90deg,transparent,var(--mode-accent2),transparent);
  animation:scanLine 2.7s linear infinite
}
.mode .name{display:block;font-size:14px;font-weight:950}
.mode .note{display:block;margin-top:4px;font-size:10px;line-height:1.4;color:#8398ad}
.mode.on .name{color:var(--mode-accent2);text-shadow:0 0 16px rgba(var(--mode-rgb),.18)}
.filters{
  position:sticky;top:66px;z-index:90;margin:0 0 20px;padding:9px;
  background:rgba(6,14,24,.94);backdrop-filter:blur(16px);
  border:1px solid rgba(var(--accent-rgb),.2);border-radius:15px
}
.chips{display:flex;gap:8px;flex-wrap:wrap;overflow-x:auto;scrollbar-width:none}.chips::-webkit-scrollbar{display:none}
.chip{
  border:1px solid #294259;background:#0b1927;color:#9cb0c3;
  border-radius:999px;padding:9px 13px;white-space:nowrap;cursor:pointer;
  font-size:11px;font-weight:850;transition:.18s
}
.chip:hover{transform:translateY(-1px);border-color:rgba(var(--accent-rgb),.45)}
.chip.on{background:var(--accent);border-color:var(--accent);color:#04110d;box-shadow:0 0 24px rgba(var(--accent-rgb),.18)}
.chip.disabled{opacity:.35;cursor:not-allowed}
.notice{
  display:none;margin:0 0 18px;padding:14px 15px;border-radius:13px;
  background:#24151b;border:1px solid #6e3344;color:#ffb1bf;font-size:12px;line-height:1.55
}
.modepending{
  display:none;padding:20px;border:1px solid rgba(var(--mode-rgb),.3);border-radius:20px;
  background:linear-gradient(155deg,rgba(var(--mode-rgb),.09),#0a1724 48%,#07121d);
  margin:16px 0 28px;box-shadow:0 18px 52px rgba(0,0,0,.2);animation:panelIn .4s ease both
}
.previewtop{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:16px}
.modepending h2{margin:0 0 7px;font-size:27px;letter-spacing:-.03em}.modepending p{margin:0;color:#a2b5c6;line-height:1.65;font-size:13px;max-width:820px}
.modepending .pill{display:inline-flex;padding:7px 10px;border-radius:999px;border:1px solid rgba(var(--mode-rgb),.38);color:var(--mode-accent2);font-size:10px;font-weight:900;white-space:nowrap}
.previewstats{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin:15px 0 20px}
.pstat{padding:12px;border-radius:12px;background:#071521;border:1px solid #20384e}
.pstat b{display:block;font-size:22px;margin-top:5px;letter-spacing:-.03em}
.previewalert{padding:11px 13px;border-radius:11px;background:rgba(244,197,92,.07);border:1px solid rgba(244,197,92,.24);color:#d9c99e;font-size:10px;line-height:1.55;margin-bottom:17px}
.previewgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.pcard{position:relative;overflow:hidden;padding:15px;border-radius:15px;background:linear-gradient(180deg,#0d1c2b,#081420);border:1px solid #21394f;animation:cardIn .45s ease both}
.pcard:before{content:"";position:absolute;left:0;top:0;bottom:0;width:2px;background:var(--mode-accent)}
.pcard:hover{transform:translateY(-3px);border-color:rgba(var(--mode-rgb),.48);box-shadow:0 16px 40px rgba(var(--mode-rgb),.08)}
.pcardhead{display:flex;justify-content:space-between;gap:8px;align-items:center}.pcardsym{font-size:18px;font-weight:950}.pcardbadge{font-size:8px;font-weight:950;padding:5px 7px;border-radius:999px;color:var(--mode-accent2);background:rgba(var(--mode-rgb),.09);border:1px solid rgba(var(--mode-rgb),.24)}
.pprice{font-size:26px;font-weight:950;letter-spacing:-.04em;margin:10px 0 2px}.pmeta{font-size:9px;color:#7990a5}
.pmetrics{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.pmetric{padding:8px;border-radius:9px;background:#07131f;border:1px solid #193147}.pmetric span{display:block;color:#6f869b;font-size:7px;text-transform:uppercase}.pmetric b{display:block;margin-top:3px;font-size:11px}
.fresh{
  margin:15px 0 18px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
  padding:12px 14px;border-radius:13px;background:#081624;border:1px solid #20364d;color:#8fa5b9;font-size:11px
}
.fresh b{color:var(--accent2)}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin-bottom:20px}
.stat{
  min-height:108px;position:relative;overflow:hidden;padding:16px 17px;border-radius:16px;
  background:linear-gradient(180deg,#0d1b2a,#091521);border:1px solid #20374d
}
.stat:after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:linear-gradient(90deg,transparent,var(--accent),transparent)}
.lab{font-size:9px;color:#7890a6;text-transform:uppercase;letter-spacing:.09em;font-weight:800}
.num{font-size:31px;font-weight:950;letter-spacing:-.04em;margin-top:8px}
.stat small{display:block;color:#758ba0;font-size:10px;margin-top:6px}
.g{color:#39e69d}.y{color:#f4c866}.b{color:#72adff}
.search{display:flex;gap:9px;padding:10px;margin:0 0 29px;border-radius:14px;background:#081522;border:1px solid #21374d}
.search input{flex:1;min-width:0;padding:12px 13px;border-radius:10px;background:#050f19;color:#fff;border:1px solid #2a435b;font-size:13px}
.search input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(var(--accent-rgb),.08)}
.primary,.load{
  border:1px solid rgba(var(--accent-rgb),.4);border-radius:10px;
  padding:11px 16px;background:linear-gradient(135deg,rgba(var(--accent-rgb),.35),rgba(var(--accent-rgb),.12));
  color:var(--accent2);font-weight:900;font-size:11px;cursor:pointer
}
.section{margin:0 0 34px;padding:16px;border-radius:18px;background:#0a1724;border:1px solid #1f3449;box-shadow:0 12px 34px rgba(0,0,0,.12);transition:.2s ease}
.section:hover{transform:translateY(-1px)}
.section-best{background:linear-gradient(180deg,rgba(34,197,94,.08),#0a1724 46%);border-color:rgba(34,197,94,.30);border-top:3px solid #22c55e}
.section-open{background:linear-gradient(180deg,rgba(20,184,166,.08),#0a1724 46%);border-color:rgba(20,184,166,.30);border-top:3px solid #14b8a6}
.section-near{background:linear-gradient(180deg,rgba(245,158,11,.085),#0a1724 46%);border-color:rgba(245,158,11,.30);border-top:3px solid #f59e0b}
.section-watch{background:linear-gradient(180deg,rgba(139,92,246,.08),#0a1724 46%);border-color:rgba(139,92,246,.30);border-top:3px solid #8b5cf6}
.section-history{background:linear-gradient(180deg,rgba(56,189,248,.08),#0a1724 46%);border-color:rgba(56,189,248,.30);border-top:3px solid #38bdf8}
.section-best .title{color:#4ade80}.section-open .title{color:#2dd4bf}.section-near .title{color:#fbbf24}.section-watch .title{color:#a78bfa}.section-history .title{color:#67e8f9}
.section-best .titlewrap{border-left-color:#22c55e}.section-open .titlewrap{border-left-color:#14b8a6}.section-near .titlewrap{border-left-color:#f59e0b}.section-watch .titlewrap{border-left-color:#8b5cf6}.section-history .titlewrap{border-left-color:#38bdf8}
.head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:13px}
.titlewrap{padding-left:12px;border-left:3px solid var(--accent)}
.title{font-size:22px;font-weight:950;letter-spacing:-.025em}
.desc{font-size:11px;color:#8196aa;margin-top:4px}
.count{font-size:10px;font-weight:900;color:var(--accent2);padding:6px 9px;border:1px solid rgba(var(--accent-rgb),.3);border-radius:999px}
.quality{
  position:relative;overflow:hidden;margin-bottom:34px;padding:18px;border-radius:19px;
  background:linear-gradient(145deg,rgba(var(--accent-rgb),.1),#0b1826 47%,#091522);
  border:1px solid rgba(var(--accent-rgb),.34);box-shadow:0 15px 45px rgba(0,0,0,.17)
}
.quality:after{content:"";position:absolute;width:180px;height:180px;border-radius:50%;right:-70px;top:-90px;background:rgba(var(--accent-rgb),.07)}
.summary{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:16px 0 18px}
.sum{padding:12px;background:#081521;border:1px solid #20374d;border-radius:12px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{
  overflow:hidden;border-radius:16px;background:linear-gradient(180deg,#0d1c2b,#091521);
  border:1px solid #21394f;box-shadow:0 12px 34px rgba(0,0,0,.14);transition:.18s
}
.card:hover{transform:translateY(-3px);border-color:rgba(var(--accent-rgb),.48);box-shadow:0 16px 40px rgba(var(--accent-rgb),.07)}
.ctop{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:14px 15px;border-bottom:1px solid #1a3045;background:linear-gradient(90deg,rgba(var(--accent-rgb),.07),transparent)}
.sym{font-size:18px;font-weight:950;letter-spacing:-.02em}
.badge{padding:6px 8px;border-radius:999px;background:#142638;color:#a8b9ca;font-size:8px;font-weight:950}
.badge.open{color:#58ebb0;background:#103426}.badge.near{color:#f4cd74;background:#352c16}
.body{padding:14px 15px}.muted{color:#7f94a8;font-size:10px}.price{font-size:28px;font-weight:950;letter-spacing:-.04em;margin-top:3px}
.levels,.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:13px}
.box{padding:9px;border-radius:10px;background:#07131f;border:1px solid #193147}.box b{display:block;margin-top:4px;font-size:12px}
.tablewrap{overflow:auto;border-radius:15px;border:1px solid #223a51;background:#091622;box-shadow:0 12px 34px rgba(0,0,0,.12)}
table{width:100%;border-collapse:collapse;min-width:760px}
th,td{padding:12px 13px;text-align:left;border-bottom:1px solid #152b3f;font-size:11px}
th{position:sticky;top:0;background:#0d1b2a;color:#8198ad;font-size:9px;text-transform:uppercase;letter-spacing:.06em}
tbody tr:hover td{background:rgba(var(--accent-rgb),.045)}
.empty{padding:24px;border:1px dashed #29435b;border-radius:13px;text-align:center;color:#7f95aa;font-size:12px}
.loadw{text-align:center;margin-top:13px}
.foot{margin-top:42px;padding-top:24px;border-top:1px solid #1b3044;text-align:center;color:#657b90;font-size:10px;line-height:1.7}
.loading{opacity:.5;pointer-events:none}
@keyframes heroIn{from{opacity:0;transform:translateY(12px) scale(.992)}to{opacity:1;transform:none}}
@keyframes panelIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes cardIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes scanLine{from{left:-35%}to{left:105%}}
@keyframes heroSweep{from{left:-32%}to{left:125%}}
@keyframes orbFloat{from{transform:translate3d(0,0,0) scale(1)}to{transform:translate3d(-6vw,-8vh,0) scale(1.12)}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important}}
@media(max-width:1050px){.grid{grid-template-columns:repeat(2,1fr)}.stats{grid-template-columns:repeat(2,1fr)}}
@media(max-width:720px){
  .navin{padding:12px}.navmeta{display:none}.page{padding:18px 11px 38px}.hero{padding:20px 17px}.hero:after{font-size:82px;right:10px}
  .modebar{grid-template-columns:1fr}.filters{top:60px}.grid{grid-template-columns:1fr}.summary{grid-template-columns:1fr}.search{flex-direction:column}.previewgrid{grid-template-columns:1fr}.previewstats{grid-template-columns:repeat(2,1fr)}.previewtop{flex-direction:column}
  .stats{gap:8px}.stat{min-height:94px;padding:13px}.num{font-size:27px}.title{font-size:20px}
  .tablewrap{border:0;overflow:visible;background:transparent}table,thead,tbody,tr,th,td{display:block;width:100%;min-width:0}thead{display:none}
  tbody{display:grid;gap:10px}tr{display:grid;grid-template-columns:1fr 1fr;border:1px solid #21384e;border-radius:14px;overflow:hidden;background:#0b1927}
  td{padding:10px 11px}td:before{content:attr(data-l);display:block;font-size:7px;text-transform:uppercase;color:#71879b;margin-bottom:3px}
  td:first-child{grid-column:1/-1;background:#0e1e2d;font-size:14px;font-weight:900}.load{width:100%}
}

/* FIBEDGE PROFESSIONAL DASHBOARD - RENDER PRODUCTION */
html,body{background:#07111d!important;color:#edf6ff!important}
body{background:radial-gradient(circle at 82% 0%,rgba(53,130,210,.10),transparent 28%),linear-gradient(180deg,#071321,#050d17 100%)!important}
.nav{background:rgba(6,16,29,.96)!important;border-bottom:1px solid #18334d!important;box-shadow:none!important}
.hero{background:transparent!important;box-shadow:none!important;border-color:#18334d!important;padding:26px 28px!important}
.hero h1{font-size:36px!important;line-height:1.05!important;margin-bottom:0!important}
.hero-guide{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:20px}
.guide-item{padding:13px 14px;border:1px solid #1b3b56;border-radius:11px;background:rgba(8,25,42,.72)}
.guide-item b{display:block;color:#eaf6ff;font-size:11px}
.guide-item b span{margin-right:5px;color:#54baf4}
.guide-item p{margin:6px 0 0!important;font-size:9px!important;line-height:1.5!important;color:#7894ad!important}
.premium-guide{border-color:rgba(231,190,91,.42)} .premium-guide b span{color:#e7be5b}
.status-guide{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.status-guide span{padding:7px 10px;border:1px solid #1b3952;border-radius:20px;background:#081827;color:#7791aa;font-size:8px}
.status-guide b{margin-right:4px;color:#dcecff}
.filters{background:#0a1928!important;border:1px solid #1a3853!important;box-shadow:none!important}
.chip{background:#0d1e2f!important;border:1px solid #23435f!important;color:#8fa7bd!important;transition:.18s ease}
.chip:hover{color:#dff3ff!important;border-color:#438bc5!important}
.chip.on{background:#1683c4!important;border-color:#45b9f1!important;color:#fff!important;box-shadow:0 0 14px rgba(50,170,240,.15)}
.pro-modes{display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:12px!important;margin:20px 0!important}
.pro-modes .mode{min-height:138px;padding:18px!important;display:flex;flex-direction:column;align-items:flex-start;text-align:left;border-radius:14px!important;border:1px solid #234660!important;background:linear-gradient(145deg,#0f2235,#091725)!important;box-shadow:none!important;transition:.18s ease}
.pro-modes .mode:hover{transform:translateY(-2px);border-color:#4aa6df!important}
.pro-modes .mode.on{border-color:#55bdf5!important;background:linear-gradient(145deg,#113354,#0b1d2f)!important}
.strategy-no{font-size:10px;font-weight:900;color:#54baf4}
.pro-modes .name{margin-top:6px;font-size:15px!important;font-weight:800!important;color:#f1f8ff!important}
.strategy-rate{margin-top:14px;font-size:28px;line-height:1;color:#69c7ff}
.rate-label{margin-top:5px;font-size:8px;text-transform:uppercase;letter-spacing:.08em;color:#738da4}
.premiumplus-tab{border-color:rgba(231,190,91,.45)!important}
.premiumplus-tab .strategy-no,.premiumplus-tab .strategy-rate{color:#e7be5b!important}
.premiumplus-tab.on{border-color:#e7be5b!important;background:linear-gradient(145deg,#28251b,#101c29)!important}
#watch,#hist,.section-watch,.section-history{display:none!important}
.stats{grid-template-columns:repeat(3,1fr)!important}
.stats .stat:nth-child(4){display:none!important}
.section,.quality,.modepending,.stat,.pstat{background:#0a1928!important;border:1px solid #1d3a54!important;box-shadow:none!important;border-radius:14px!important}
.section-best{border-top:2px solid #459fe3!important}.section-open{border-top:2px solid #35d0a5!important}.section-near{border-top:2px solid #e0b456!important}
.card,.pcard{background:linear-gradient(145deg,#0d2032,#091725)!important;border:1px solid #1d3f5c!important;box-shadow:none!important;border-radius:13px!important;transition:.18s ease;overflow:hidden}
.card:hover,.pcard:hover{transform:translateY(-2px);border-color:#4399d2!important}
.ctop,.pcardhead{padding:15px!important;border-bottom:1px solid #183750!important;display:flex!important;align-items:flex-start!important;justify-content:space-between!important}
.sym,.pcardsym{color:#f2f8ff!important}.price,.pprice{color:#f5faff!important}
.card-status{margin-top:4px;color:#55bdf5;font-size:8px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.gold-status{color:#e7be5b!important}
.simplemetrics,.pmetrics{padding:14px;display:grid!important;grid-template-columns:repeat(3,1fr)!important;gap:8px!important}
.simplemetrics>div,.pmetric{background:#071521!important;border:1px solid #18364f!important;border-radius:8px!important;padding:9px!important}
.simplemetrics span,.pmetric span{display:block;font-size:7px;color:#6f879e!important;text-transform:uppercase;letter-spacing:.06em}
.simplemetrics b,.pmetric b{display:block;margin-top:4px;color:#dcecff!important;font-size:11px}
.pmetric.special{border-color:rgba(90,170,235,.35)!important}
.premiumplus-card{border-color:rgba(231,190,91,.35)!important}.premium-pill{border-color:rgba(231,190,91,.45)!important;color:#e7be5b!important}
.title{color:#f0f7ff!important}.desc,.muted,.lab,.pmeta{color:#7891a8!important}
@keyframes cardIn{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
.card,.pcard{animation:cardIn .25s ease both}
@media(max-width:950px){.pro-modes,.hero-guide{grid-template-columns:repeat(2,1fr)!important}}
@media(max-width:600px){.pro-modes{grid-template-columns:1fr 1fr!important;gap:8px!important}.pro-modes .mode{min-height:122px;padding:13px!important}.strategy-rate{font-size:23px}.hero-guide{grid-template-columns:1fr!important}.simplemetrics,.pmetrics{grid-template-columns:repeat(2,1fr)!important}}
@media(prefers-reduced-motion:reduce){.card,.pcard,.mode{animation:none!important;transition:none!important}}

</style>
</head>
<body class="theme-all">
<div class="nav">
  <div class="navin">
    <div class="brand"><div class="brandmark">F</div><span>FibEdge <b>786</b></span></div>
    <div class="navmeta">NSE setup intelligence<br><strong>GitHub data • auto refresh</strong></div>
  </div>
</div>

<main class="page" id="page">
  <section class="hero">
    <div class="eyebrow">Dashboard guide</div>
    <h1>Read the setup in seconds.</h1>

    <div class="hero-guide">
      <div class="guide-item">
        <b><span>01</span> Classic FibEdge</b>
        <p>Broadest 0.786 scanner for valid Fibonacci structures.</p>
      </div>
      <div class="guide-item">
        <b><span>02</span> Clean Swings</b>
        <p>Major high-to-low swings with cleaner recovery structure.</p>
      </div>
      <div class="guide-item">
        <b><span>03</span> Premium Clean</b>
        <p>Selective big-swing recovery tier. Historical resolved win rate 56.36%.</p>
      </div>
      <div class="guide-item premium-guide">
        <b><span>04</span> Premium+ V1</b>
        <p>Rare behavior-confirmed setup after the daily candle closes.</p>
      </div>
    </div>

    <div class="status-guide">
      <span><b>Best Setups</b> highest priority</span>
      <span><b>Open Now</b> entry triggered</span>
      <span><b>Near Structure</b> approaching 0.786</span>
    </div>

    <div class="herofoot">
      <span class="tag live">LIVE DASHBOARD</span>
      <span class="tag">0.786 ENTRY</span>
      <span class="tag">0.500 STOP</span>
      <span class="tag">1.260 TARGET</span>
    </div>
  </section>

  <div class="modebar pro-modes" id="modebar">
    <button class="mode on" data-mode="CLASSIC">
      <span class="strategy-no">01</span>
      <span class="name">Classic FibEdge</span>
      <strong class="strategy-rate">30.44%</strong>
      <span class="rate-label">Historical win rate</span>
    </button>
    <button class="mode" data-mode="CLEAN">
      <span class="strategy-no">02</span>
      <span class="name">Clean Swings</span>
      <strong class="strategy-rate">42.52%</strong>
      <span class="rate-label">Historical win rate</span>
    </button>
    <button class="mode" data-mode="PREMIUM">
      <span class="strategy-no">03</span>
      <span class="name">Premium Clean</span>
      <strong class="strategy-rate">56.36%</strong>
      <span class="rate-label">Resolved historical win rate</span>
    </button>
    <button class="mode premiumplus-tab" data-mode="PREMIUMPLUS">
      <span class="strategy-no">04</span>
      <span class="name">Premium+ V1</span>
      <strong class="strategy-rate">76.97%</strong>
      <span class="rate-label">Historical win rate</span>
    </button>
  </div>

  <div class="filters"><div class="chips" id="chips"></div></div>
  <div class="notice" id="error"></div>

  <section class="modepending" id="modePending"><div id="modeContent"></div></section>

  <div id="classicArea">
    <div class="fresh"><span>Latest timestamp: <b id="latest">Loading…</b></span><span>Universe: <b id="universeLabel">All</b></span></div>

    <div class="stats">
      <div class="stat"><div class="lab">Stocks Scanned</div><div class="num" id="total">—</div><small>Current universe</small></div>
      <div class="stat"><div class="lab">Open Now</div><div class="num g" id="openN">—</div><small>0.786 already triggered</small></div>
      <div class="stat"><div class="lab">Near Structure</div><div class="num y" id="nearN">—</div><small>Highest-priority approach</small></div>
      <div class="stat"><div class="lab">Waiting</div><div class="num b" id="waitN">—</div><small>Developing setups</small></div>
    </div>

    <form class="search" id="searchForm">
      <input id="searchInput" placeholder="Search stock symbol…" autocomplete="off">
      <button class="primary" type="submit">Search</button>
    </form>

    <div class="section" id="searchSection" style="display:none">
      <div class="head"><div class="titlewrap"><div class="title">Search Results</div><div class="desc" id="searchDesc"></div></div><div class="count" id="searchCount">0</div></div>
      <div id="searchRows"></div>
    </div>

    <div class="quality section-best">
      <div class="titlewrap"><div class="title">Best Setups</div><div class="desc">Highest-priority setups from the selected strategy.</div></div>
      <div class="summary">
        <div class="sum"><div class="lab">Strong Now</div><div class="num g" id="strongN">0</div></div>
        <div class="sum"><div class="lab">Good Setups</div><div class="num b" id="goodNTop">0</div></div>
        <div class="sum"><div class="lab">Quality Watch</div><div class="num y" id="qwatchN">0</div></div>
      </div>
      <div id="strongRows"></div>
    </div>

    <div class="section section-open" id="open">
      <div class="head"><div class="titlewrap"><div class="title">Open Now</div><div class="desc">Entry condition has triggered.</div></div><div class="count" id="openCount">0</div></div>
      <div id="openRows"></div><div class="loadw" id="openLoad"></div>
    </div>

    <div class="section section-near" id="near">
      <div class="head"><div class="titlewrap"><div class="title">Near Structure</div><div class="desc">Approaching the 0.786 entry structure.</div></div><div class="count" id="nearCount">0</div></div>
      <div id="nearRows"></div>
    </div>

    <div class="section section-watch" id="watch">
      <div class="head"><div class="titlewrap"><div class="title">Watchlist</div><div class="desc">Waiting setups within 10% of 0.786.</div></div><div class="count" id="watchCount">0</div></div>
      <div id="watchRows"></div><div class="loadw" id="watchLoad"></div>
    </div>

    <div class="section section-history" id="hist">
      <div class="head"><div class="titlewrap"><div class="title">Good Historical Setups</div><div class="desc">Positive historical setups ranked by quality and speed.</div></div><div class="count" id="goodCount">0</div></div>
      <div id="goodRows"></div><div class="loadw" id="goodLoad"></div>
    </div>
  </div>

  <div class="foot">FibEdge 786 • Research use only • Market data may be delayed • Manual chart confirmation recommended</div>
</main>

<script>
const BASE='https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/';
const URLS={
  signals:BASE+'FIBEDGE_LATEST_SIGNALS.csv',
  opp:BASE+'FIBEDGE_BEST_OPPORTUNITIES_V3.csv',
  map:BASE+'STOCK_UNIVERSE_MAPPING.csv',
  premiumPlus:BASE+'netlify_site/premium_plus_candidates.json'
};

const FILTERS=[
  {key:'ALL',label:'All'},
  {key:'NIFTY50',label:'NIFTY 50'},
  {key:'FNO',label:'F&O'},
  {key:'NIFTY500',label:'NIFTY 500',requires:'NIFTY500'},
  {key:'MIDSMALL400',label:'MidSmall 400',requires:'MIDSMALL400'},
  {key:'SMALLCAP250',label:'Smallcap 250'},
  {key:'MICROCAP250',label:'Microcap 250'}
];

let DATA={signals:[],opp:[],map:[],premiumPlus:{candidates:[]}};
let selected='ALL',mode='CLASSIC',openLimit=24,watchLimit=100,qualityLimit=20;

function esc(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
function parseCSV(text){const rows=[];let row=[],field='',q=false;for(let i=0;i<text.length;i++){const c=text[i],n=text[i+1];if(q){if(c==='"'&&n==='"'){field+='"';i++}else if(c==='"'){q=false}else field+=c}else{if(c==='"')q=true;else if(c===','){row.push(field);field=''}else if(c==='\n'){row.push(field);rows.push(row);row=[];field=''}else if(c!=='\r')field+=c}}if(field.length||row.length){row.push(field);rows.push(row)}const head=rows.shift()||[];return rows.filter(r=>r.some(x=>x!=='')).map(r=>Object.fromEntries(head.map((h,i)=>[h.trim(),r[i]??''])))} 
async function fetchCSV(url){const sep=url.includes('?')?'&':'?';const r=await fetch(url+sep+'t='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('Could not load '+url.split('/').pop()+' ('+r.status+')');return parseCSV((await r.text()).replace(/^\uFEFF/,''))}
async function fetchJSON(url){const sep=url.includes('?')?'&':'?';const r=await fetch(url+sep+'t='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('Could not load '+url.split('/').pop()+' ('+r.status+')');return await r.json()}
function sym(v){return String(v||'').replace('.NS','').trim().toUpperCase()}
function num(v,d=2){const x=Number(v);return Number.isFinite(x)?x.toFixed(d):'-'}
function pct(v,plus=false){const x=Number(v);if(!Number.isFinite(x))return '-';return(plus&&x>0?'+':'')+x.toFixed(2)+'%'}
function hasMapColumn(key){return key==='ALL'||(DATA.map.length&&Object.prototype.hasOwnProperty.call(DATA.map[0],key))}
function currentFilterSet(){if(selected==='ALL'||!hasMapColumn(selected))return null;return new Set(DATA.map.filter(r=>String(r[selected]||'').toUpperCase()==='YES').map(r=>sym(r.SYMBOL)))}
function filtered(rows){const set=currentFilterSet();return set?rows.filter(r=>set.has(sym(r.Symbol))):[...rows]}
function mapPreviewWarning(){return selected!=='ALL'&&!hasMapColumn(selected)}
function byDistance(a,b){return Number(a['Distance %'])-Number(b['Distance %'])}
function byAbsDistance(a,b){return Math.abs(Number(a['Distance %']))-Math.abs(Number(b['Distance %']))}
function signalRow(r){
  const high=Number(r.High),low=Number(r.Low);
  const decline=(Number.isFinite(high)&&Number.isFinite(low)&&high>0)?((high-low)/high*100):null;
  const swing=daysBetween(r['High Date'],r['Low Date']);
  return{
    Symbol:sym(r.Symbol),Price:num(r.Price),Status:r.Status||'-',
    Entry:num(r.Entry),SL:num(r.SL),Target:num(r.Target),
    Distance:pct(r['Distance %']),
    Decline:Number.isFinite(decline)?decline.toFixed(1)+'%':'-',
    Swing:swing?swing+'d':'-',
    Time:r['Price Time']||'-'
  }
}
function qualityRow(r){return{Symbol:sym(r.Symbol),Price:num(r.Price),Entry:num(r.Entry),State:r['Current State']||'-',Grade:r['Live Grade']||'-',Speed:r['Speed Group']||'-',Win:pct(r['Win Rate %']),Exp:pct(r['Expectancy %'],true)}}
function cards(rows,badge){
  if(!rows.length)return'<div class="empty">No setups right now.</div>';
  return '<div class="grid">'+rows.map(r=>
    '<div class="card">'+
      '<div class="ctop">'+
        '<div><div class="sym">'+esc(r.Symbol)+'</div><div class="card-status">'+esc(badge)+'</div></div>'+
        '<div class="price">₹'+esc(r.Price)+'</div>'+
      '</div>'+
      '<div class="simplemetrics">'+
        '<div><span>Entry</span><b>₹'+esc(r.Entry)+'</b></div>'+
        '<div><span>Stop</span><b>₹'+esc(r.SL)+'</b></div>'+
        '<div><span>Target</span><b>₹'+esc(r.Target)+'</b></div>'+
        '<div><span>Distance</span><b>'+esc(r.Distance)+'</b></div>'+
        '<div><span>Decline</span><b>'+esc(r.Decline||'-')+'</b></div>'+
        '<div><span>Swing</span><b>'+esc(r.Swing||'-')+'</b></div>'+
      '</div>'+
    '</div>'
  ).join('')+'</div>';
}
function strongCards(rows){return cards(rows,'BEST')}
function table(rows,kind){if(!rows.length)return'<div class="empty">No matching setups.</div>';let cols;if(kind==='quality')cols=[['Symbol','Symbol'],['State','State'],['Price','Price'],['Entry','Entry'],['Grade','Grade'],['Win','Win Rate'],['Exp','Expectancy'],['Speed','Speed']];else if(kind==='search')cols=[['Symbol','Symbol'],['Price','Price'],['Status','Status'],['Entry','Entry'],['SL','SL'],['Target','Target'],['Distance','Distance'],['Time','Price Time']];else cols=[['Symbol','Symbol'],['Price','Price'],['Distance','Distance'],['Entry','Entry'],['SL','SL'],['Target','Target'],['Time','Price Time']];return'<div class="tablewrap"><table><thead><tr>'+cols.map(c=>'<th>'+c[1]+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(c=>'<td data-l="'+esc(c[1])+'">'+esc(r[c[0]]??'-')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>'}
function btn(id,label,fn){document.getElementById(id).innerHTML='<button class="load" type="button">'+label+'</button>';document.querySelector('#'+id+' button').onclick=fn}
function clearBtn(id){document.getElementById(id).innerHTML=''}
function setTheme(){document.body.className='theme-'+selected.toLowerCase()+' mode-'+mode.toLowerCase();document.getElementById('universeLabel').textContent=FILTERS.find(x=>x.key===selected)?.label||'All'}
function renderModes(){document.querySelectorAll('.mode').forEach(b=>{b.classList.toggle('on',b.dataset.mode===mode);b.onclick=()=>{mode=b.dataset.mode;setTheme();renderModes();renderModeView()}})}
function daysBetween(a,b){const x=new Date(a),y=new Date(b);return(!isNaN(x)&&!isNaN(y))?Math.round((y-x)/86400000):0}
function cleanPreviewRows(){
  let sig=filtered(DATA.signals).filter(r=>['OPEN','NEAR 0.786','WAITING FOR 0.786','ENTRY AREA'].includes(r.Status));
  const oppMap=new Map(filtered(DATA.opp).map(r=>[sym(r.Symbol),r]));
  let rows=sig.map(r=>{
    const high=Number(r.High),low=Number(r.Low);
    const decline=(Number.isFinite(high)&&Number.isFinite(low)&&high>0)?((high-low)/high*100):0;
    const swing=daysBetween(r['High Date'],r['Low Date']);
    const q=oppMap.get(sym(r.Symbol))||{};
    return {...r,_decline:decline,_swing:swing,_quality:Number(q['Opportunity Score V3'])||0,_grade:q['Live Grade']||q.Grade||'-',_opp:q.Opportunity||'-'};
  }).filter(r=>r._decline>=20&&r._swing>=40);
  if(!rows.length) rows=sig.map(r=>({...r,_decline:0,_swing:daysBetween(r['High Date'],r['Low Date']),_quality:0,_grade:'-',_opp:'-'}));
  rows.sort((a,b)=>Math.abs(Number(a['Distance %']))-Math.abs(Number(b['Distance %'])));
  return rows;
}
function previewCards(rows,premium){
  if(!rows.length)return'<div class="empty">No setups right now.</div>';
  return '<div class="previewgrid">'+rows.slice(0,12).map((r,i)=>{
    const status=r.Status==='NEAR 0.786'?'NEAR':r.Status==='OPEN'?'OPEN':r.Status==='ENTRY AREA'?'OPEN':'';
    const recovery=premium && r['Recovery Efficiency']!==undefined
      ? '<div class="pmetric special"><span>Recovery Eff.</span><b>'+esc(num(r['Recovery Efficiency']))+'</b></div>'
      : '';
    return '<div class="pcard" style="animation-delay:'+(i*35)+'ms">'+
      '<div class="pcardhead"><div><div class="pcardsym">'+esc(sym(r.Symbol))+'</div><div class="card-status">'+esc(status)+'</div></div><div class="pprice">₹'+esc(num(r.Price))+'</div></div>'+
      '<div class="pmetrics">'+
        '<div class="pmetric"><span>Entry</span><b>₹'+esc(num(r.Entry))+'</b></div>'+
        '<div class="pmetric"><span>Stop</span><b>₹'+esc(num(r.SL))+'</b></div>'+
        '<div class="pmetric"><span>Target</span><b>₹'+esc(num(r.Target))+'</b></div>'+
        '<div class="pmetric"><span>Distance</span><b>'+esc(pct(r['Distance %']))+'</b></div>'+
        '<div class="pmetric"><span>Decline</span><b>'+esc(r._decline?r._decline.toFixed(1)+'%':'-')+'</b></div>'+
        '<div class="pmetric"><span>Swing</span><b>'+esc(r._swing?r._swing+'d':'-')+'</b></div>'+
        recovery+
      '</div>'+
    '</div>';
  }).join('')+'</div>';
}
function previewSection(title,desc,count,html,cls){
  return '<div class="section '+(cls||'')+'"><div class="head"><div class="titlewrap"><div class="title">'+esc(title)+'</div><div class="desc">'+esc(desc)+'</div></div><div class="count">'+count+'</div></div>'+html+'</div>';
}
function premiumPlusRows(){
  let rows=[...(DATA.premiumPlus?.candidates||[])];
  const set=currentFilterSet();
  if(set)rows=rows.filter(r=>set.has(sym(r.symbol)));
  return rows;
}
function premiumPlusCards(rows){
  if(!rows.length)return'<div class="empty"><b>No Premium+ setup today.</b><br><br>Waiting for the frozen V1 conditions to appear after a completed daily candle.</div>';
  return '<div class="previewgrid">'+rows.map((r,i)=>
    '<div class="pcard premiumplus-card" style="animation-delay:'+(i*35)+'ms">'+
      '<div class="pcardhead"><div><div class="pcardsym">'+esc(sym(r.symbol))+'</div><div class="card-status gold-status">CONFIRMED</div></div><div class="pprice">₹'+esc(num(r.close))+'</div></div>'+
      '<div class="pmetrics">'+
        '<div class="pmetric"><span>Entry 0.786</span><b>₹'+esc(num(r.fib_0786))+'</b></div>'+
        '<div class="pmetric"><span>Stop</span><b>₹'+esc(num(r.sl))+'</b></div>'+
        '<div class="pmetric"><span>Target</span><b>₹'+esc(num(r.target))+'</b></div>'+
        '<div class="pmetric"><span>Decline</span><b>'+esc(num(r.decline_pct))+'%</b></div>'+
        '<div class="pmetric"><span>Swing</span><b>'+esc(r.swing_days||'-')+'d</b></div>'+
        '<div class="pmetric special"><span>Lower Wick</span><b>'+esc(num(r.lower_wick_pct))+'%</b></div>'+
        '<div class="pmetric special"><span>Compression</span><b>'+esc(num(r.compression_3v10))+'</b></div>'+
        '<div class="pmetric special"><span>Close above 0.786</span><b>+'+esc(num(r.close_vs_786_pct))+'%</b></div>'+
      '</div>'+
    '</div>'
  ).join('')+'</div>';
}
function renderPremiumPlusView(){
  const rows=premiumPlusRows();
  const uni=FILTERS.find(x=>x.key===selected)?.label||'All';
  const html=
    '<div class="previewtop"><div><h2>Premium+ V1</h2><p>Frozen behavior-confirmed setup. Historical backtest: 234 wins / 304 resolved = 76.97%.</p></div><span class="pill premium-pill">PREMIUM+ V1</span></div>'+
    '<div class="previewstats">'+
      '<div class="pstat"><div class="lab">Candidates</div><b>'+rows.length+'</b></div>'+
      '<div class="pstat"><div class="lab">Historical Win Rate</div><b>76.97%</b></div>'+
      '<div class="pstat"><div class="lab">Resolved Backtest</div><b>304</b></div>'+
      '<div class="pstat"><div class="lab">Universe</div><b style="font-size:14px;margin-top:10px">'+esc(uni.toUpperCase())+'</b></div>'+
    '</div>'+
    previewSection('Best Setups','Confirmed Premium+ candidates after the daily close.',rows.length,premiumPlusCards(rows),'section-best')+
    previewSection('Open Now','Premium+ uses next-session entry after confirmation.',0,'<div class="empty">No separate open list for Premium+.</div>','section-open')+
    previewSection('Near Structure','Premium+ only appears after full confirmation.',0,'<div class="empty">Near-only structures are intentionally excluded from Premium+.</div>','section-near');
  document.getElementById('modeContent').innerHTML=html;
}
function renderModeView(){
  const classic=document.getElementById('classicArea'),pending=document.getElementById('modePending');
  if(mode==='CLASSIC'){classic.style.display='block';pending.style.display='none';render();return}
  classic.style.display='none';pending.style.display='block';
  if(mode==='PREMIUMPLUS'){renderPremiumPlusView();return}

  let rows=cleanPreviewRows();
  const premium=mode==='PREMIUM';
  if(premium)rows=[...rows].sort((a,b)=>(b._quality-a._quality)||Math.abs(Number(a['Distance %']))-Math.abs(Number(b['Distance %'])));

  const uni=FILTERS.find(x=>x.key===selected)?.label||'All';
  const visibleRows=rows.filter(r=>['OPEN','ENTRY AREA','NEAR 0.786'].includes(r.Status));
  const openRows=visibleRows.filter(r=>['OPEN','ENTRY AREA'].includes(r.Status)).sort(byAbsDistance);
  const nearRows=visibleRows.filter(r=>r.Status==='NEAR 0.786').sort(byDistance);
  const bestRows=[...visibleRows].sort((a,b)=>premium
    ?((b._quality-a._quality)||Math.abs(Number(a['Distance %']))-Math.abs(Number(b['Distance %'])))
    :(Math.abs(Number(a['Distance %']))-Math.abs(Number(b['Distance %'])))).slice(0,9);

  const modeTitle=premium?'Premium Clean':'Clean Swings';
  const modeText=premium
    ?'Selective big-swing recovery tier. Historical resolved win rate: 56.36%.'
    :'Major high-to-low swing structures. Historical win rate: 42.52%.';
  const pill=premium?'PREMIUM CLEAN':'CLEAN SWINGS';

  const html=
    '<div class="previewtop"><div><h2>'+modeTitle+'</h2><p>'+modeText+'</p></div><span class="pill">'+pill+'</span></div>'+
    '<div class="previewstats">'+
      '<div class="pstat"><div class="lab">Best Setups</div><b>'+bestRows.length+'</b></div>'+
      '<div class="pstat"><div class="lab">Open Now</div><b>'+openRows.length+'</b></div>'+
      '<div class="pstat"><div class="lab">Near Structure</div><b>'+nearRows.length+'</b></div>'+
      '<div class="pstat"><div class="lab">Universe</div><b style="font-size:14px;margin-top:10px">'+esc(uni.toUpperCase())+'</b></div>'+
    '</div>'+
    previewSection('Best Setups','Highest-priority setups from this strategy.',bestRows.length,previewCards(bestRows,premium),'section-best')+
    previewSection('Open Now','Entry condition has triggered.',openRows.length,previewCards(openRows,premium),'section-open')+
    previewSection('Near Structure','Approaching the 0.786 entry structure.',nearRows.length,previewCards(nearRows,premium),'section-near');

  document.getElementById('modeContent').innerHTML=html;
}
function renderChips(){const box=document.getElementById('chips');box.innerHTML=FILTERS.map(f=>'<button class="chip '+(f.key===selected?'on ':'')+'" data-k="'+f.key+'">'+f.label+(f.requires&&!hasMapColumn(f.requires)?' · PREVIEW':'')+'</button>').join('');box.querySelectorAll('button').forEach(b=>b.onclick=()=>{selected=b.dataset.k;openLimit=24;watchLimit=100;qualityLimit=20;setTheme();renderChips();renderModeView();history.replaceState(null,'','?universe='+encodeURIComponent(selected))})}
function latestLabel(rows){const ds=rows.map(r=>new Date(r['Price Time'])).filter(d=>!isNaN(d));if(!ds.length)return'Unavailable';const d=new Date(Math.max(...ds.map(x=>x.getTime())));return d.toLocaleString('en-IN',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:true})}
function renderSearch(sig){const q=document.getElementById('searchInput').value.trim().toUpperCase(),sec=document.getElementById('searchSection');if(!q){sec.style.display='none';return}const rs=sig.filter(r=>sym(r.Symbol).includes(q)).map(signalRow);sec.style.display='block';document.getElementById('searchDesc').textContent=q;document.getElementById('searchCount').textContent=rs.length;document.getElementById('searchRows').innerHTML=table(rs,'search')}
function render(){
  if(mode!=='CLASSIC')return;
  const page=document.getElementById('page'),err=document.getElementById('error');
  page.classList.add('loading');err.style.display='none';
  try{
    const sig=filtered(DATA.signals),opp=filtered(DATA.opp);
    const od=sig.filter(r=>r.Status==='OPEN').sort(byAbsDistance);
    const nd=sig.filter(r=>r.Status==='NEAR 0.786').sort(byDistance);
    const wd=sig.filter(r=>r.Status==='WAITING FOR 0.786');
    const strong=opp.filter(r=>['ELITE NOW','STRONG NOW'].includes(r.Opportunity));
    const good=opp.filter(r=>r.Opportunity==='GOOD');
    const qw=opp.filter(r=>r.Opportunity==='WATCH');
    const sigMap=new Map(sig.map(r=>[sym(r.Symbol),r]));
    const strongSignalRows=strong.map(r=>sigMap.get(sym(r.Symbol))).filter(Boolean).map(signalRow);

    document.getElementById('latest').textContent=latestLabel(sig);
    document.getElementById('total').textContent=sig.length;
    document.getElementById('openN').textContent=od.length;
    document.getElementById('nearN').textContent=nd.length;
    document.getElementById('waitN').textContent=wd.length;
    document.getElementById('strongN').textContent=strong.length;
    document.getElementById('goodNTop').textContent=good.length;
    document.getElementById('qwatchN').textContent=qw.length;

    document.getElementById('strongRows').innerHTML=strongCards(strongSignalRows);
    document.getElementById('openCount').textContent=od.length;
    document.getElementById('openRows').innerHTML=cards(od.slice(0,openLimit).map(signalRow),'OPEN');
    document.getElementById('nearCount').textContent=nd.length;
    document.getElementById('nearRows').innerHTML=cards(nd.map(signalRow),'NEAR');

    renderSearch(sig);
  }catch(e){
    err.textContent=e.message||String(e);
    err.style.display='block';
  }finally{
    page.classList.remove('loading');
  }
}
async function loadAll(silent=false){
  const err=document.getElementById('error');
  if(!silent)document.getElementById('latest').textContent='Loading…';
  try{
    const[signals,opp,map,premiumPlus]=await Promise.all([
      fetchCSV(URLS.signals),
      fetchCSV(URLS.opp),
      fetchCSV(URLS.map),
      fetchJSON(URLS.premiumPlus).catch(()=>({candidates:[]}))
    ]);
    DATA={signals,opp,map,premiumPlus};
    renderChips();
    renderModeView();
  }catch(e){
    err.textContent='Data load failed: '+(e.message||e);
    err.style.display='block';
    document.getElementById('latest').textContent='Unavailable';
  }
}
document.getElementById('searchForm').addEventListener('submit',e=>{e.preventDefault();render()});
const q=new URLSearchParams(location.search).get('universe');
if(FILTERS.some(x=>x.key===String(q||'').toUpperCase()))selected=String(q).toUpperCase();
setTheme();renderModes();renderChips();loadAll();setInterval(()=>loadAll(true),10*60*1000);
</script>
</body>
</html>
"""


def load_latest_data():

    response = requests.get(
        GITHUB_CSV_URL,
        timeout=15,
        headers={
            "Cache-Control": "no-cache"
        }
    )

    response.raise_for_status()

    return pd.read_csv(
        io.StringIO(
            response.text
        )
    )


def clean_number(value):

    if pd.isna(value):
        return "-"

    try:
        return f"{float(value):.2f}"

    except Exception:
        return "-"


def clean_time(value):

    if pd.isna(value):
        return "-"

    try:

        dt = pd.to_datetime(
            value
        )

        return dt.strftime(
            "%d %b %Y • %I:%M %p"
        )

    except Exception:

        return str(value)


def make_rows(df):

    rows = []

    for _, row in df.iterrows():

        distance = row.get(
            "Distance %",
            None
        )

        if pd.isna(distance):

            distance_text = "-"

        else:

            distance_text = (
                f"{float(distance):.2f}%"
            )

        rows.append({

            "Symbol":
                str(row["Symbol"])
                .replace(".NS", ""),

            "Price":
                clean_number(
                    row.get("Price")
                ),

            "Status":
                row.get(
                    "Status",
                    "-"
                ),

            "Entry":
                clean_number(
                    row.get("Entry")
                ),

            "SL":
                clean_number(
                    row.get("SL")
                ),

            "Target":
                clean_number(
                    row.get("Target")
                ),

            "Distance":
                distance_text,

            "PriceTime":
                clean_time(
                    row.get("Price Time")
                )
        })

    return rows



def make_quality_rows(df):

    rows = []

    for _, row in df.iterrows():

        distance = row.get("Distance %", None)
        win_rate = row.get("Win Rate %", None)
        expectancy = row.get("Expectancy %", None)
        median_days = row.get("Median Win Days", None)

        rows.append({

            "Symbol":
                str(row.get("Symbol", "")).replace(".NS", ""),

            "CurrentState":
                str(row.get("Current State", "-")),

            "Price":
                clean_number(row.get("Price")),

            "Entry":
                clean_number(row.get("Entry")),

            "Distance":
                f"{float(distance):.2f}%"
                if not pd.isna(distance)
                else "-",

            "Grade":
                str(row.get("Live Grade", "-")),

            "WinRate":
                f"{float(win_rate):.2f}%"
                if not pd.isna(win_rate)
                else "-",

            "Trades":
                int(row.get("Resolved Trades", 0))
                if not pd.isna(row.get("Resolved Trades", None))
                else 0,

            "Expectancy":
                f"{float(expectancy):+.2f}%"
                if not pd.isna(expectancy)
                else "-",

            "MedianDays":
                f"{float(median_days):.1f} days"
                if not pd.isna(median_days)
                else "-",

            "Speed":
                str(row.get("Speed Group", "-"))
        })

    return rows


@app.route("/")
def home():

    try:

        df = load_latest_data()

        opportunity_response = requests.get(
            GITHUB_OPPORTUNITY_URL,
            timeout=15,
            headers={
                "Cache-Control": "no-cache"
            }
        )

        opportunity_response.raise_for_status()

        opportunity_df = pd.read_csv(
            io.StringIO(
                opportunity_response.text
            )
        )

    except Exception as error:

        return f"""
        <body style="
            background:#07111f;
            color:white;
            font-family:Arial;
            padding:40px;
        ">

            <h2>
                FibEdge 786
            </h2>

            <p>
                Latest market data could not be loaded.
            </p>

            <p>
                {error}
            </p>

        </body>
        """, 503


    open_df = df[
        df["Status"] == "OPEN"
    ].copy()


    near_df = df[
        df["Status"] == "NEAR 0.786"
    ].copy()


    waiting_df = df[
        df["Status"] == "WAITING FOR 0.786"
    ].copy()


    watch_df = waiting_df[
        waiting_df["Distance %"] <= 10
    ].copy()


    if not open_df.empty:

        open_df = open_df.sort_values(
            "Distance %",
            key=lambda s: s.abs(),
            na_position="last"
        )


    if not near_df.empty:

        near_df = near_df.sort_values(
            "Distance %",
            na_position="last"
        )


    if not watch_df.empty:

        watch_df = watch_df.sort_values(
            "Distance %",
            na_position="last"
        )



    if opportunity_df.empty:

        strong_df = pd.DataFrame()
        good_df = pd.DataFrame()
        quality_watch_df = pd.DataFrame()

    else:

        strong_df = opportunity_df[
            opportunity_df["Opportunity"].isin([
                "ELITE NOW",
                "STRONG NOW"
            ])
        ].copy()

        good_df = opportunity_df[
            opportunity_df["Opportunity"] == "GOOD"
        ].copy()

        quality_watch_df = opportunity_df[
            opportunity_df["Opportunity"] == "WATCH"
        ].copy()

    try:
        quality_limit = max(
            20,
            int(request.args.get("quality_limit", 20))
        )
    except Exception:
        quality_limit = 20


    search = (
        request.args
        .get("q", "")
        .strip()
        .upper()
    )

    try:
        open_limit = max(
            24,
            min(
                int(request.args.get("open_limit", 24)),
                len(open_df)
            )
        )
    except Exception:
        open_limit = 24

    try:
        watch_limit = max(
            100,
            min(
                int(request.args.get("watch_limit", 100)),
                len(watch_df)
            )
        )
    except Exception:
        watch_limit = 100


    search_df = pd.DataFrame()


    if search:

        search_df = df[
            df["Symbol"]
            .astype(str)
            .str.upper()
            .str.contains(
                search,
                regex=False
            )
        ].copy()


    valid_times = pd.to_datetime(
        df["Price Time"],
        errors="coerce"
    ).dropna()


    if len(valid_times) > 0:

        latest_timestamp = (
            valid_times
            .max()
            .strftime(
                "%d %b %Y • %I:%M %p"
            )
        )

    else:

        latest_timestamp = (
            "Unavailable"
        )


    return render_template_string(

        HTML,

        total_count=len(df),

        open_count=len(open_df),

        near_count=len(near_df),

        waiting_count=len(waiting_df),

        strong_rows=make_quality_rows(strong_df),

        good_rows=make_quality_rows(good_df),

        good_count=len(good_df),

        quality_watch_count=len(quality_watch_df),

        quality_limit=quality_limit,

        open_limit=open_limit,
        watch_limit=watch_limit,

        open_rows=make_rows(
            open_df
        ),

        near_rows=make_rows(
            near_df
        ),

        watch_rows=make_rows(
            watch_df
        ),

        search_rows=make_rows(
            search_df
        ),

        search=search,

        latest_timestamp=
            latest_timestamp
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5007,
        debug=True
    )
