from flask import Flask, render_template_string, request
import pandas as pd
import io
import requests
from pathlib import Path

app = Flask(__name__)

OPPORTUNITY_FILE = "FIBEDGE_BEST_OPPORTUNITIES_V3.csv"

GITHUB_CSV_URL = (
    "https://raw.githubusercontent.com/"
    "adesh-dhandre/fibedge786/master/"
    "FIBEDGE_LATEST_SIGNALS.csv"
)

HTML = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>FibEdge 786</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;

            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Roboto,
                Arial,
                sans-serif;

            background:
                linear-gradient(
                    180deg,
                    #06101d 0%,
                    #081421 100%
                );

            color: #edf3fb;
        }

        .navbar {
            position: sticky;
            top: 0;
            z-index: 100;

            background:
                rgba(8, 20, 33, 0.96);

            backdrop-filter:
                blur(12px);

            border-bottom:
                1px solid #1a2b40;
        }

        .navbar-inner {
            max-width: 1450px;

            margin: auto;

            padding:
                16px 24px;

            display: flex;

            align-items: center;

            justify-content:
                space-between;

            gap: 20px;
        }

        .brand {
            display: flex;

            align-items: center;

            gap: 12px;
        }

        .brand-icon {
            width: 38px;
            height: 38px;

            border-radius: 10px;

            display: flex;

            align-items: center;

            justify-content: center;

            background:
                linear-gradient(
                    135deg,
                    #20d47b,
                    #00a866
                );

            color: #04140c;

            font-weight: 900;

            font-size: 18px;
        }

        .brand-text {
            font-size: 21px;

            font-weight: 800;

            letter-spacing:
                0.5px;
        }

        .brand-text span {
            color: #20d47b;
        }

        .nav-note {
            color: #8ea2b9;

            font-size: 12px;
        }

        .page {
            max-width: 1450px;

            margin: auto;

            padding:
                28px 24px 55px;
        }

        .hero h1 {
            margin: 0;

            font-size:
                clamp(
                    28px,
                    4vw,
                    42px
                );

            line-height: 1.05;
        }

        .hero p {
            color: #8193aa;

            margin-top: 10px;

            font-size: 14px;
        }

        .strategy-chip {
            margin-top: 15px;

            display:
                inline-flex;

            flex-wrap: wrap;

            gap: 8px;

            background:
                #0d1c2e;

            border:
                1px solid #1d3148;

            padding:
                9px 12px;

            border-radius: 10px;

            color: #9dafc5;

            font-size: 12px;
        }

        .strategy-chip strong {
            color: #d9e5f2;
        }

        .freshness {
            margin-top: 24px;

            background:
                linear-gradient(
                    90deg,
                    rgba(24,109,75,0.16),
                    rgba(20,39,58,0.45)
                );

            border:
                1px solid #1f5b43;

            border-radius: 12px;

            padding:
                13px 16px;

            display: flex;

            justify-content:
                space-between;

            align-items: center;

            gap: 16px;

            font-size: 13px;
        }

        .fresh-value {
            color: #20d47b;

            font-weight: 700;
        }

        .delay-note {
            color: #7f91a8;

            text-align: right;
        }

        .stats-grid {
            display: grid;

            grid-template-columns:
                repeat(
                    4,
                    minmax(180px, 1fr)
                );

            gap: 14px;

            margin:
                26px 0 32px;
        }

        .stat-card {
            background:
                linear-gradient(
                    180deg,
                    #0d1b2c,
                    #0a1726
                );

            border:
                1px solid #1b2d43;

            border-radius: 14px;

            padding: 19px;
        }

        .stat-label {
            color: #788ba2;

            font-size: 11px;

            letter-spacing: 0.8px;

            text-transform:
                uppercase;
        }

        .stat-number {
            margin-top: 7px;

            font-size: 29px;

            font-weight: 800;
        }

        .stat-sub {
            margin-top: 6px;

            color: #62758d;

            font-size: 11px;
        }

        .green {
            color: #20d47b;
        }

        .yellow {
            color: #f2c45e;
        }

        .blue {
            color: #62a8ff;
        }

        .search-panel {
            background:
                #0b1828;

            border:
                1px solid #1a2c42;

            border-radius: 13px;

            padding: 16px;

            margin-bottom: 30px;
        }

        .search-form {
            display: flex;

            gap: 10px;
        }

        .search-form input {
            flex: 1;

            background:
                #07121f;

            border:
                1px solid #26394f;

            border-radius: 9px;

            padding:
                13px 14px;

            color: white;

            font-size: 14px;

            outline: none;
        }

        .search-form button {
            border: 0;

            border-radius: 9px;

            padding:
                12px 20px;

            background:
                #1a2c42;

            color: #edf4fc;

            font-weight: 700;

            cursor: pointer;
        }

        .section {
            margin-bottom: 36px;
        }

        .section-head {
            display: flex;

            justify-content:
                space-between;

            align-items:
                flex-end;

            gap: 15px;

            margin-bottom: 14px;
        }

        .section-title {
            font-size: 20px;

            font-weight: 800;
        }

        .section-desc {
            color: #70839a;

            font-size: 12px;

            margin-top: 4px;
        }

        .count-pill {
            background:
                #0e1d2f;

            border:
                1px solid #21364f;

            color: #9dafc5;

            border-radius: 20px;

            padding:
                6px 10px;

            font-size: 11px;
        }

        .signal-grid {
            display: grid;

            grid-template-columns:
                repeat(
                    3,
                    minmax(0, 1fr)
                );

            gap: 14px;
        }

        .signal-card {
            background:
                linear-gradient(
                    180deg,
                    #0d1b2c,
                    #091625
                );

            border:
                1px solid #1b2d43;

            border-radius: 14px;

            overflow: hidden;
        }

        .signal-top {
            padding:
                15px 16px;

            border-bottom:
                1px solid #18283b;

            display: flex;

            justify-content:
                space-between;

            align-items: center;
        }

        .symbol {
            font-size: 18px;

            font-weight: 800;
        }

        .badge {
            border-radius: 20px;

            padding:
                6px 9px;

            font-size: 10px;

            font-weight: 800;
        }

        .badge-open {
            background:
                rgba(32,212,123,0.14);

            color: #20d47b;
        }

        .badge-near {
            background:
                rgba(242,196,94,0.14);

            color: #f2c45e;
        }

        .signal-body {
            padding: 16px;
        }

        .current-label {
            color: #708299;

            font-size: 11px;

            text-transform:
                uppercase;
        }

        .current-price {
            margin-top: 4px;

            font-size: 27px;

            font-weight: 800;
        }

        .price-time {
            margin-top: 4px;

            color: #687b92;

            font-size: 10px;
        }

        .levels {
            margin-top: 17px;

            display: grid;

            grid-template-columns:
                repeat(3, 1fr);

            gap: 8px;
        }

        .level {
            background:
                #0d1d30;

            border-radius: 9px;

            padding: 10px;
        }

        .level-name {
            color: #6f829a;

            font-size: 9px;

            text-transform:
                uppercase;
        }

        .level-value {
            margin-top: 4px;

            font-size: 13px;

            font-weight: 700;
        }

        .entry-value {
            color: #62a8ff;
        }

        .sl-value {
            color: #ff7480;
        }

        .target-value {
            color: #27d883;
        }

        .table-wrap {
            overflow-x: auto;

            background:
                #0b1828;

            border:
                1px solid #1a2d43;

            border-radius: 13px;
        }

        table {
            width: 100%;

            border-collapse:
                collapse;

            min-width: 1000px;
        }

        th {
            text-align: left;

            padding:
                13px 14px;

            color: #76899f;

            font-size: 10px;

            text-transform:
                uppercase;

            border-bottom:
                1px solid #22354b;

            background:
                #0c1a2a;
        }

        td {
            padding:
                13px 14px;

            border-bottom:
                1px solid #152538;

            font-size: 12px;
        }

        tr:hover {
            background:
                #102139;
        }

        .empty {
            background:
                #0b1828;

            border:
                1px dashed #294057;

            border-radius: 12px;

            color: #6f8197;

            padding: 26px;

            text-align: center;
        }

        .footer {
            margin-top: 45px;

            border-top:
                1px solid #17283a;

            padding-top: 25px;

            text-align: center;

            color: #5c7188;

            font-size: 11px;

            line-height: 1.7;
        }


        .quality-zone {
            margin: 30px 0 42px;
            padding: 22px;
            background: linear-gradient(180deg, rgba(18,41,61,.92), rgba(8,22,37,.96));
            border: 1px solid #29445f;
            border-radius: 16px;
        }

        .quality-zone-title {
            font-size: 23px;
            font-weight: 850;
        }

        .quality-zone-desc {
            color: #8296ad;
            font-size: 12px;
            margin: 6px 0 20px;
            line-height: 1.6;
        }

        .quality-summary {
            display: grid;
            grid-template-columns: repeat(3, minmax(150px, 1fr));
            gap: 10px;
            margin-bottom: 22px;
        }

        .quality-summary-card {
            background: #091828;
            border: 1px solid #203951;
            border-radius: 11px;
            padding: 14px;
        }

        .quality-summary-label {
            color: #71859c;
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: .6px;
        }

        .quality-summary-number {
            margin-top: 5px;
            font-size: 24px;
            font-weight: 850;
        }

        .quality-card {
            background: linear-gradient(180deg, #102238, #0b192a);
            border: 1px solid #29445d;
            border-radius: 14px;
            overflow: hidden;
        }

        .quality-card-head {
            padding: 15px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            border-bottom: 1px solid #20364c;
        }

        .quality-badges {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }

        .q-badge {
            padding: 5px 8px;
            border-radius: 20px;
            font-size: 9px;
            font-weight: 850;
        }

        .q-strong {
            color: #20d47b;
            background: rgba(32,212,123,.13);
        }

        .q-grade {
            color: #f2c45e;
            background: rgba(242,196,94,.13);
        }

        .q-speed {
            color: #b7c9dc;
            background: #172a3f;
        }

        .quality-body {
            padding: 16px;
        }

        .quality-price-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            align-items: flex-end;
        }

        .quality-price {
            font-size: 25px;
            font-weight: 850;
        }

        .quality-state {
            color: #9bb0c6;
            font-size: 11px;
            text-align: right;
        }

        .quality-metrics {
            margin-top: 16px;
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }

        .quality-metric {
            background: #0b1b2d;
            border-radius: 9px;
            padding: 10px;
        }

        .quality-metric-label {
            color: #657a91;
            font-size: 9px;
            text-transform: uppercase;
        }

        .quality-metric-value {
            margin-top: 4px;
            font-size: 13px;
            font-weight: 750;
        }

        .quality-divider {
            margin: 26px 0 16px;
            border-top: 1px solid #20364c;
        }

        .quality-subtitle {
            font-size: 17px;
            font-weight: 800;
            margin-bottom: 12px;
        }

        @media(max-width: 1050px) {

            .stats-grid {
                grid-template-columns:
                    repeat(2,1fr);
            }

            .signal-grid {
                grid-template-columns:
                    repeat(2,1fr);
            }
        }

        @media(max-width: 700px) {

            .navbar-inner {
                padding:
                    13px 15px;
            }

            .nav-note {
                display: none;
            }

            .page {
                padding:
                    20px 14px 40px;
            }

            .stats-grid {
                grid-template-columns:
                    repeat(2,1fr);

                gap: 9px;
            }

            .signal-grid {
                grid-template-columns:
                    1fr;
            }

            .search-form {
                flex-direction:
                    column;
            }

            .quality-summary {
                grid-template-columns: 1fr;
            }

            .quality-metrics {
                grid-template-columns: repeat(2, 1fr);
            }

            .freshness {
                display: block;
            }

            .delay-note {
                text-align: left;

                margin-top: 7px;
            }
        }

    </style>
</head>

<body>

<div class="navbar">
    <div class="navbar-inner">

        <div class="brand">
            <div class="brand-icon">786</div>

            <div class="brand-text">
                FibEdge <span>786</span>
            </div>
        </div>

        <div class="nav-note">
            Auto-updated NSE Signal Dashboard
        </div>

    </div>
</div>

<div class="page">

    <div class="hero">

        <h1>
            NSE Fibonacci Signal Dashboard
        </h1>

        <p>
            Latest automatically published FibEdge signals
            across the NSE equity universe.
        </p>

        <div class="strategy-chip">

            <span>
                Decline:
                <strong>8%+</strong>
            </span>

            <span>•</span>

            <span>
                Swing:
                <strong>15+ days</strong>
            </span>

            <span>•</span>

            <span>
                Entry:
                <strong>0.786</strong>
            </span>

            <span>•</span>

            <span>
                SL:
                <strong>0.500</strong>
            </span>

            <span>•</span>

            <span>
                Target:
                <strong>1.260</strong>
            </span>

        </div>

    </div>

    <div class="freshness">

        <div>
            Latest market timestamp:

            <span class="fresh-value">
                {{ latest_timestamp }}
            </span>
        </div>

        <div class="delay-note">
            Auto-updated via GitHub Actions • Yahoo Finance may be delayed
        </div>

    </div>

    <div class="stats-grid">

        <div class="stat-card">
            <div class="stat-label">Stocks Scanned</div>
            <div class="stat-number">{{ total_count }}</div>
            <div class="stat-sub">Latest automated update</div>
        </div>

        <div class="stat-card">
            <div class="stat-label">Open Signals</div>
            <div class="stat-number green">{{ open_count }}</div>
            <div class="stat-sub">0.786 triggered</div>
        </div>

        <div class="stat-card">
            <div class="stat-label">Near 0.786</div>
            <div class="stat-number yellow">{{ near_count }}</div>
            <div class="stat-sub">Within 2% of entry</div>
        </div>

        <div class="stat-card">
            <div class="stat-label">Waiting</div>
            <div class="stat-number blue">{{ waiting_count }}</div>
            <div class="stat-sub">Active structures</div>
        </div>

    </div>

    <div class="search-panel">

        <form
            class="search-form"
            method="GET"
        >
            <input
                type="text"
                name="q"
                value="{{ search }}"
                placeholder="Search HCG, BHEL, RELIANCE, HEG..."
            >

            <button type="submit">
                Search
            </button>
        </form>

    </div>

    {% if search %}

    <div class="section">

        <div class="section-head">

            <div>
                <div class="section-title">
                    Search Results
                </div>

                <div class="section-desc">
                    {{ search }}
                </div>
            </div>

            <div class="count-pill">
                {{ search_rows|length }}
            </div>

        </div>

        {% if search_rows %}

        <div class="table-wrap">

            <table>

                <thead>

                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Status</th>
                        <th>Entry</th>
                        <th>SL</th>
                        <th>Target</th>
                        <th>Distance</th>
                        <th>Price Time</th>
                    </tr>

                </thead>

                <tbody>

                    {% for row in search_rows %}

                    <tr>
                        <td>
                            <strong>{{ row.Symbol }}</strong>
                        </td>

                        <td>₹{{ row.Price }}</td>
                        <td>{{ row.Status }}</td>
                        <td>₹{{ row.Entry }}</td>
                        <td>₹{{ row.SL }}</td>
                        <td>₹{{ row.Target }}</td>
                        <td>{{ row.Distance }}</td>
                        <td>{{ row.PriceTime }}</td>
                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

        {% else %}

        <div class="empty">
            No matching stock found.
        </div>

        {% endif %}

    </div>

    {% endif %}

    


    

    

    
<div class="quality-zone" id="quality-opportunities">

        <div class="quality-zone-title">
            🔥 Best Setups Now
        </div>

        <div class="quality-zone-desc">
            Separate quality-ranking section based on the 5-year
            meaningful-swing backtest. Historical quality, win rate,
            expectancy, sample size and target speed are combined with
            the current 0.786 position.
        </div>

        <div class="quality-summary">

            <div class="quality-summary-card">
                <div class="quality-summary-label">Strong Now</div>
                <div class="quality-summary-number green">
                    {{ strong_rows|length }}
                </div>
            </div>

            <div class="quality-summary-card">
                <div class="quality-summary-label">Good Setups</div>
                <div class="quality-summary-number blue">
                    {{ good_count }}
                </div>
            </div>

            <div class="quality-summary-card">
                <div class="quality-summary-label">Quality Watch</div>
                <div class="quality-summary-number yellow">
                    {{ quality_watch_count }}
                </div>
            </div>

        </div>

        <div class="quality-subtitle">
            Strong Now
        </div>

        {% if strong_rows %}

        <div class="signal-grid">

            {% for row in strong_rows %}

            <div class="quality-card">

                <div class="quality-card-head">

                    <div class="symbol">
                        {{ row.Symbol }}
                    </div>

                    <div class="quality-badges">
                        <span class="q-badge q-strong">STRONG NOW</span>
                        <span class="q-badge q-grade">Grade {{ row.Grade }}</span>
                        <span class="q-badge q-speed">{{ row.Speed }}</span>
                    </div>

                </div>

                <div class="quality-body">

                    <div class="quality-price-row">

                        <div>
                            <div class="current-label">Current Price</div>
                            <div class="quality-price">₹{{ row.Price }}</div>
                        </div>

                        <div class="quality-state">
                            {{ row.CurrentState }}
                        </div>

                    </div>

                    <div class="quality-metrics">

                        <div class="quality-metric">
                            <div class="quality-metric-label">Entry 0.786</div>
                            <div class="quality-metric-value entry-value">
                                ₹{{ row.Entry }}
                            </div>
                        </div>

                        <div class="quality-metric">
                            <div class="quality-metric-label">Distance</div>
                            <div class="quality-metric-value">
                                {{ row.Distance }}
                            </div>
                        </div>

                        <div class="quality-metric">
                            <div class="quality-metric-label">Win Rate</div>
                            <div class="quality-metric-value">
                                {{ row.WinRate }}
                            </div>
                        </div>

                        <div class="quality-metric">
                            <div class="quality-metric-label">Historical Trades</div>
                            <div class="quality-metric-value">
                                {{ row.Trades }}
                            </div>
                        </div>

                        <div class="quality-metric">
                            <div class="quality-metric-label">Expectancy</div>
                            <div class="quality-metric-value">
                                {{ row.Expectancy }}
                            </div>
                        </div>

                        <div class="quality-metric">
                            <div class="quality-metric-label">Median Win Time</div>
                            <div class="quality-metric-value">
                                {{ row.MedianDays }}
                            </div>
                        </div>

                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No Strong Now setups at the moment.
        </div>

        {% endif %}

    </div>

<div class="section" id="open-signals">

        <div class="section-head">

            <div>
                <div class="section-title">
                    Open Signals
                </div>

                <div class="section-desc">
                    Entry has already triggered.
                </div>
            </div>

            <div class="count-pill">
                {{ open_rows|length }}
            </div>

        </div>

        {% if open_rows %}

        <div class="signal-grid">

            {% for row in open_rows[:open_limit] %}

            <div class="signal-card">

                <div class="signal-top">

                    <div class="symbol">
                        {{ row.Symbol }}
                    </div>

                    <div class="badge badge-open">
                        OPEN
                    </div>

                </div>

                <div class="signal-body">

                    <div class="current-label">
                        Latest Price
                    </div>

                    <div class="current-price">
                        ₹{{ row.Price }}
                    </div>

                    <div class="price-time">
                        {{ row.PriceTime }}
                    </div>

                    <div class="levels">

                        <div class="level">

                            <div class="level-name">
                                Entry
                            </div>

                            <div class="level-value entry-value">
                                ₹{{ row.Entry }}
                            </div>

                        </div>

                        <div class="level">

                            <div class="level-name">
                                Stop
                            </div>

                            <div class="level-value sl-value">
                                ₹{{ row.SL }}
                            </div>

                        </div>

                        <div class="level">

                            <div class="level-name">
                                Target
                            </div>

                            <div class="level-value target-value">
                                ₹{{ row.Target }}
                            </div>

                        </div>

                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% if open_rows|length > open_limit %}

        <div style="text-align:center; margin-top:18px;">

            <a
                href="/?open_limit={{ open_limit + 24 }}&watch_limit={{ watch_limit }}#open-signals"
                style="
                    display:inline-block;
                    text-decoration:none;
                    background:#1a2c42;
                    color:#edf4fc;
                    padding:11px 18px;
                    border-radius:9px;
                    font-size:12px;
                    font-weight:800;
                "
            >
                Load More Open Signals
            </a>

            <div style="
                margin-top:8px;
                color:#66798f;
                font-size:11px;
            ">
                Showing {{ [open_limit, open_rows|length]|min }}
                of {{ open_rows|length }}
            </div>

        </div>

        {% endif %}

        {% else %}

        <div class="empty">
            No open signals.
        </div>

        {% endif %}

    </div>

<div class="section">

        <div class="section-head">

            <div>
                <div class="section-title">
                    Near 0.786 Entry
                </div>

                <div class="section-desc">
                    Highest-priority upcoming setups.
                </div>
            </div>

            <div class="count-pill">
                {{ near_rows|length }}
            </div>

        </div>

        {% if near_rows %}

        <div class="signal-grid">

            {% for row in near_rows %}

            <div class="signal-card">

                <div class="signal-top">
                    <div class="symbol">
                        {{ row.Symbol }}
                    </div>

                    <div class="badge badge-near">
                        NEAR ENTRY
                    </div>
                </div>

                <div class="signal-body">

                    <div class="current-label">
                        Latest Price
                    </div>

                    <div class="current-price">
                        ₹{{ row.Price }}
                    </div>

                    <div class="price-time">
                        {{ row.PriceTime }}
                    </div>

                    <div class="levels">

                        <div class="level">
                            <div class="level-name">
                                Entry
                            </div>

                            <div class="level-value entry-value">
                                ₹{{ row.Entry }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-name">
                                Stop
                            </div>

                            <div class="level-value sl-value">
                                ₹{{ row.SL }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-name">
                                Target
                            </div>

                            <div class="level-value target-value">
                                ₹{{ row.Target }}
                            </div>
                        </div>

                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No near-entry setups right now.
        </div>

        {% endif %}

    </div>

<div class="section" id="watchlist">

        <div class="section-head">

            <div>

                <div class="section-title">
                    Watchlist
                </div>

                <div class="section-desc">
                    Waiting setups within 10% of 0.786.
                </div>

            </div>

            <div class="count-pill">
                {{ watch_rows|length }}
            </div>

        </div>

        {% if watch_rows %}

        <div class="table-wrap">

            <table>

                <thead>

                    <tr>
                        <th>Symbol</th>
                        <th>Price</th>
                        <th>Distance</th>
                        <th>Entry</th>
                        <th>SL</th>
                        <th>Target</th>
                        <th>Price Time</th>
                    </tr>

                </thead>

                <tbody>

                    {% for row in watch_rows[:watch_limit] %}

                    <tr>
                        <td>
                            <strong>{{ row.Symbol }}</strong>
                        </td>

                        <td>₹{{ row.Price }}</td>
                        <td class="blue">{{ row.Distance }}</td>
                        <td>₹{{ row.Entry }}</td>
                        <td>₹{{ row.SL }}</td>
                        <td>₹{{ row.Target }}</td>
                        <td>{{ row.PriceTime }}</td>
                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

        {% if watch_rows|length > watch_limit %}

        <div style="text-align:center; margin-top:18px;">

            <a
                href="/?open_limit={{ open_limit }}&watch_limit={{ watch_limit + 100 }}#watchlist"
                style="
                    display:inline-block;
                    text-decoration:none;
                    background:#1a2c42;
                    color:#edf4fc;
                    padding:11px 18px;
                    border-radius:9px;
                    font-size:12px;
                    font-weight:800;
                "
            >
                Load More Watchlist Stocks
            </a>

            <div style="
                margin-top:8px;
                color:#66798f;
                font-size:11px;
            ">
                Showing {{ [watch_limit, watch_rows|length]|min }}
                of {{ watch_rows|length }}
            </div>

        </div>

        {% endif %}

        {% else %}

        <div class="empty">
            No nearby waiting setups.
        </div>

        {% endif %}

    </div>


    <div class="section" id="good-historical-setups">

        <div class="section-head">

            <div>

                <div class="section-title">
                    📊 Good Historical Setups
                </div>

                <div class="section-desc">
                    Positive historical FibEdge setups ranked by
                    win rate, expectancy, sample size and target speed.
                </div>

            </div>

            <div class="count-pill">
                {{ good_count }}
            </div>

        </div>


        {% if good_rows %}

        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>State</th>
                        <th>Price</th>
                        <th>Entry</th>
                        <th>Distance</th>
                        <th>Grade</th>
                        <th>Win Rate</th>
                        <th>Trades</th>
                        <th>Expectancy</th>
                        <th>Median Win</th>
                        <th>Speed</th>
                    </tr>
                </thead>

                <tbody>

                    {% for row in good_rows[:quality_limit] %}

                    <tr>
                        <td><strong>{{ row.Symbol }}</strong></td>
                        <td>{{ row.CurrentState }}</td>
                        <td>₹{{ row.Price }}</td>
                        <td>₹{{ row.Entry }}</td>
                        <td>{{ row.Distance }}</td>
                        <td>{{ row.Grade }}</td>
                        <td>{{ row.WinRate }}</td>
                        <td>{{ row.Trades }}</td>
                        <td>{{ row.Expectancy }}</td>
                        <td>{{ row.MedianDays }}</td>
                        <td>{{ row.Speed }}</td>
                    </tr>

                    {% endfor %}

                </tbody>
            </table>
        </div>

        {% if good_count > quality_limit %}

        <div style="text-align:center; margin-top:18px;">

            <a
                href="/?quality_limit={{ quality_limit + 20 }}&open_limit={{ open_limit }}&watch_limit={{ watch_limit }}#quality-opportunities"
                style="
                    display:inline-block;
                    text-decoration:none;
                    background:#1a2c42;
                    color:#edf4fc;
                    padding:11px 18px;
                    border-radius:9px;
                    font-size:12px;
                    font-weight:800;
                "
            >
                Load More Good Setups
            </a>

            <div style="
                margin-top:8px;
                color:#66798f;
                font-size:11px;
            ">
                Showing {{ [quality_limit, good_count]|min }}
                of {{ good_count }}
            </div>

        </div>

        {% endif %}

        {% else %}

        <div class="empty">
            No Good setups at the moment.
        </div>

        {% endif %}

    

    </div>



    <div class="footer">

        FibEdge 786 • NSE Fibonacci Research Scanner

        <br>

        Market data is refreshed automatically by GitHub Actions.

        <br>

        Yahoo Finance data may be delayed relative to NSE.

        <br><br>

        Research use only. Not financial advice.

    </div>

</div>

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

        if Path(OPPORTUNITY_FILE).exists():
            opportunity_df = pd.read_csv(OPPORTUNITY_FILE)
        else:
            opportunity_df = pd.DataFrame()

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
