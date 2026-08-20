from flask import Flask, render_template_string, request, redirect, url_for
import pandas as pd
import subprocess
import os
from datetime import datetime

app = Flask(__name__)

DATA_FILE = "FIBEDGE_LATEST_SIGNALS.csv"
REFRESH_SCRIPT = "fib_price_refresh.py"


HTML = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

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


        /* =========================
           TOP NAVIGATION
        ========================= */

        .navbar {
            position: sticky;
            top: 0;
            z-index: 100;

            background:
                rgba(8, 20, 33, 0.96);

            backdrop-filter: blur(12px);

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
            letter-spacing: 0.5px;
        }

        .brand-text span {
            color: #20d47b;
        }

        .nav-right {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .scanner-status {
            display: flex;
            align-items: center;
            gap: 8px;

            color: #9cadc1;
            font-size: 13px;
        }

        .status-dot {
            width: 9px;
            height: 9px;

            border-radius: 50%;
            background: #20d47b;

            box-shadow:
                0 0 12px
                rgba(32, 212, 123, 0.8);
        }

        .refresh-btn {
            text-decoration: none;

            background: #20d47b;
            color: #03130b;

            font-size: 13px;
            font-weight: 800;

            border-radius: 9px;

            padding:
                10px 15px;

            transition: 0.2s ease;
        }

        .refresh-btn:hover {
            transform:
                translateY(-1px);

            opacity: 0.92;
        }


        /* =========================
           MAIN WRAPPER
        ========================= */

        .page {
            max-width: 1450px;
            margin: auto;

            padding:
                28px 24px 55px;
        }


        /* =========================
           HERO
        ========================= */

        .hero {
            display: flex;
            justify-content:
                space-between;
            align-items:
                flex-end;

            gap: 20px;

            margin-bottom: 24px;
        }

        .hero-left h1 {
            margin: 0;

            font-size:
                clamp(
                    28px,
                    4vw,
                    42px
                );

            line-height: 1.05;
            letter-spacing:
                -0.5px;
        }

        .hero-left p {
            color: #8193aa;

            margin:
                10px 0 0;

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


        /* =========================
           DATA FRESHNESS
        ========================= */

        .freshness {
            background:
                linear-gradient(
                    90deg,
                    rgba(24, 109, 75, 0.16),
                    rgba(20, 39, 58, 0.45)
                );

            border:
                1px solid #1f5b43;

            border-radius: 12px;

            padding:
                13px 16px;

            margin-bottom: 24px;

            display: flex;
            justify-content:
                space-between;
            align-items: center;

            gap: 16px;

            font-size: 13px;
        }

        .fresh-left {
            display: flex;
            gap: 9px;
            align-items: center;
        }

        .fresh-label {
            color: #95a8bc;
        }

        .fresh-value {
            color: #20d47b;
            font-weight: 700;
        }

        .delay-note {
            color: #7f91a8;
            text-align: right;
        }


        /* =========================
           KPI CARDS
        ========================= */

        .stats-grid {
            display: grid;

            grid-template-columns:
                repeat(
                    4,
                    minmax(180px, 1fr)
                );

            gap: 14px;

            margin-bottom: 32px;
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

            box-shadow:
                0 10px 30px
                rgba(0, 0, 0, 0.12);
        }

        .stat-label {
            color: #788ba2;

            font-size: 11px;

            letter-spacing: 0.8px;

            text-transform: uppercase;
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

        .red {
            color: #ff6f7d;
        }


        /* =========================
           SEARCH
        ========================= */

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

        .search-form input:focus {
            border-color:
                #20d47b;
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

        .search-hint {
            margin-top: 9px;

            color: #657890;

            font-size: 11px;
        }


        /* =========================
           SECTIONS
        ========================= */

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


        /* =========================
           SIGNAL CARDS
        ========================= */

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

            transition: 0.18s ease;
        }

        .signal-card:hover {
            transform:
                translateY(-2px);

            border-color:
                #294663;
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

            letter-spacing:
                0.5px;
        }

        .badge-open {
            background:
                rgba(
                    32,
                    212,
                    123,
                    0.14
                );

            color: #20d47b;
        }

        .badge-near {
            background:
                rgba(
                    242,
                    196,
                    94,
                    0.14
                );

            color: #f2c45e;
        }

        .badge-watch {
            background:
                rgba(
                    98,
                    168,
                    255,
                    0.13
                );

            color: #62a8ff;
        }

        .badge-target {
            background:
                rgba(
                    32,
                    212,
                    123,
                    0.18
                );

            color: #4be096;
        }

        .badge-sl {
            background:
                rgba(
                    255,
                    111,
                    125,
                    0.15
                );

            color: #ff6f7d;
        }

        .signal-body {
            padding: 16px;
        }

        .current-label {
            color: #708299;

            font-size: 11px;

            text-transform:
                uppercase;

            letter-spacing:
                0.6px;
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

            padding:
                10px;
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

        .meta-row {
            margin-top: 13px;

            display: flex;

            justify-content:
                space-between;

            gap: 10px;

            padding-top: 12px;

            border-top:
                1px solid #18283c;
        }

        .meta-item {
            flex: 1;
        }

        .meta-label {
            color: #66798f;

            font-size: 9px;

            text-transform:
                uppercase;
        }

        .meta-value {
            margin-top: 3px;

            font-size: 12px;

            font-weight: 600;
        }


        /* =========================
           TABLE
        ========================= */

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

            min-width: 1100px;
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

            color: #d4deeb;
        }

        tr:hover {
            background:
                #102139;
        }

        .table-status {
            font-weight: 800;
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


        /* =========================
           FOOTER
        ========================= */

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


        /* =========================
           MOBILE
        ========================= */

        @media(max-width: 1050px) {

            .stats-grid {
                grid-template-columns:
                    repeat(2, 1fr);
            }

            .signal-grid {
                grid-template-columns:
                    repeat(2, 1fr);
            }
        }

        @media(max-width: 700px) {

            .navbar-inner {
                padding:
                    13px 15px;
            }

            .brand-text {
                font-size: 17px;
            }

            .scanner-status {
                display: none;
            }

            .refresh-btn {
                padding:
                    9px 11px;

                font-size: 11px;
            }

            .page {
                padding:
                    20px 14px
                    40px;
            }

            .hero {
                display: block;
            }

            .freshness {
                display: block;
            }

            .delay-note {
                text-align: left;

                margin-top: 7px;
            }

            .stats-grid {
                grid-template-columns:
                    repeat(2, 1fr);

                gap: 9px;
            }

            .stat-card {
                padding: 14px;
            }

            .stat-number {
                font-size: 23px;
            }

            .signal-grid {
                grid-template-columns:
                    1fr;
            }

            .search-form {
                flex-direction:
                    column;
            }

            .levels {
                grid-template-columns:
                    1fr;
            }
        }

    </style>

</head>


<body>


<div class="navbar">

    <div class="navbar-inner">

        <div class="brand">

            <div class="brand-icon">
                786
            </div>

            <div class="brand-text">
                FibEdge <span>786</span>
            </div>

        </div>


        <div class="nav-right">

            <div class="scanner-status">

                <div class="status-dot"></div>

                Scanner Online

            </div>

            <a
                href="{{ url_for('refresh_prices') }}"
                class="refresh-btn"
            >
                Refresh Prices
            </a>

        </div>

    </div>

</div>



<div class="page">


    <div class="hero">

        <div class="hero-left">

            <h1>
                NSE Fibonacci Signal Dashboard
            </h1>

            <p>
                Latest available market signals
                based on meaningful swing structure.
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

    </div>



    <div class="freshness">

        <div class="fresh-left">

            <span class="fresh-label">
                Latest market timestamp:
            </span>

            <span class="fresh-value">
                {{ latest_timestamp }}
            </span>

        </div>

        <div class="delay-note">
            Yahoo Finance intraday data may be delayed.
        </div>

    </div>



    <div class="stats-grid">

        <div class="stat-card">

            <div class="stat-label">
                Stocks Scanned
            </div>

            <div class="stat-number">
                {{ total_count }}
            </div>

            <div class="stat-sub">
                NSE equity universe
            </div>

        </div>


        <div class="stat-card">

            <div class="stat-label">
                Open Signals
            </div>

            <div class="stat-number green">
                {{ open_count }}
            </div>

            <div class="stat-sub">
                Entry already triggered
            </div>

        </div>


        <div class="stat-card">

            <div class="stat-label">
                Near 0.786
            </div>

            <div class="stat-number yellow">
                {{ near_count }}
            </div>

            <div class="stat-sub">
                Within 2% of entry
            </div>

        </div>


        <div class="stat-card">

            <div class="stat-label">
                Waiting
            </div>

            <div class="stat-number blue">
                {{ waiting_count }}
            </div>

            <div class="stat-sub">
                Active swing structures
            </div>

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
                placeholder="Search any NSE stock — HCG, BHEL, HEG, RELIANCE..."
            >

            <button type="submit">
                Search
            </button>

        </form>

        <div class="search-hint">
            Search works across the full scanned NSE universe.
        </div>

    </div>



    {% if search %}

    <div class="section">

        <div class="section-head">

            <div>

                <div class="section-title">
                    Search Results
                </div>

                <div class="section-desc">
                    Matching stocks for "{{ search }}"
                </div>

            </div>

            <div class="count-pill">
                {{ search_rows|length }} results
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
                        <th>High</th>
                        <th>Low</th>
                        <th>Entry 0.786</th>
                        <th>SL 0.500</th>
                        <th>Target 1.260</th>
                        <th>Distance</th>
                        <th>Price Time</th>
                    </tr>

                </thead>

                <tbody>

                    {% for row in search_rows %}

                    <tr>

                        <td>
                            <strong>
                                {{ row.Symbol }}
                            </strong>
                        </td>

                        <td>
                            ₹{{ row.Price }}
                        </td>

                        <td class="table-status">
                            {{ row.Status }}
                        </td>

                        <td>
                            {{ row.High }}
                        </td>

                        <td>
                            {{ row.Low }}
                        </td>

                        <td>
                            {{ row.Entry }}
                        </td>

                        <td>
                            {{ row.SL }}
                        </td>

                        <td>
                            {{ row.Target }}
                        </td>

                        <td>
                            {{ row.Distance }}
                        </td>

                        <td>
                            {{ row.PriceTime }}
                        </td>

                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

        {% else %}

        <div class="empty">
            No matching NSE stock found.
        </div>

        {% endif %}

    </div>

    {% endif %}



    <div class="section">

        <div class="section-head">

            <div>

                <div class="section-title">
                    Open Signals
                </div>

                <div class="section-desc">
                    0.786 entry has already triggered.
                </div>

            </div>

            <div class="count-pill">
                {{ open_rows|length }} signals
            </div>

        </div>


        {% if open_rows %}

        <div class="signal-grid">

            {% for row in open_rows[:18] %}

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
                                Entry 0.786
                            </div>

                            <div class="level-value entry-value">
                                ₹{{ row.Entry }}
                            </div>

                        </div>


                        <div class="level">

                            <div class="level-name">
                                Stop 0.500
                            </div>

                            <div class="level-value sl-value">
                                ₹{{ row.SL }}
                            </div>

                        </div>


                        <div class="level">

                            <div class="level-name">
                                Target 1.260
                            </div>

                            <div class="level-value target-value">
                                ₹{{ row.Target }}
                            </div>

                        </div>

                    </div>


                    <div class="meta-row">

                        <div class="meta-item">

                            <div class="meta-label">
                                Swing High
                            </div>

                            <div class="meta-value">
                                ₹{{ row.High }}
                            </div>

                        </div>


                        <div class="meta-item">

                            <div class="meta-label">
                                Swing Low
                            </div>

                            <div class="meta-value">
                                ₹{{ row.Low }}
                            </div>

                        </div>


                        <div class="meta-item">

                            <div class="meta-label">
                                Entry Move
                            </div>

                            <div class="meta-value">
                                {{ row.Distance }}
                            </div>

                        </div>

                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No open FibEdge signals.
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
                    Highest-priority stocks approaching entry.
                </div>

            </div>

            <div class="count-pill">
                {{ near_rows|length }} setups
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


                    <div class="meta-row">

                        <div class="meta-item">

                            <div class="meta-label">
                                Distance
                            </div>

                            <div class="meta-value">
                                {{ row.Distance }}
                            </div>

                        </div>


                        <div class="meta-item">

                            <div class="meta-label">
                                Swing High
                            </div>

                            <div class="meta-value">
                                ₹{{ row.High }}
                            </div>

                        </div>


                        <div class="meta-item">

                            <div class="meta-label">
                                Swing Low
                            </div>

                            <div class="meta-value">
                                ₹{{ row.Low }}
                            </div>

                        </div>

                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No stocks currently within 2% of 0.786.
        </div>

        {% endif %}

    </div>



    <div class="section">

        <div class="section-head">

            <div>

                <div class="section-title">
                    Watchlist
                </div>

                <div class="section-desc">
                    Waiting setups within 10% of entry.
                </div>

            </div>

            <div class="count-pill">
                {{ watch_rows|length }} stocks
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
                        <th>High</th>
                        <th>Low</th>
                        <th>Price Time</th>
                    </tr>

                </thead>


                <tbody>

                    {% for row in watch_rows[:100] %}

                    <tr>

                        <td>
                            <strong>
                                {{ row.Symbol }}
                            </strong>
                        </td>

                        <td>
                            ₹{{ row.Price }}
                        </td>

                        <td class="blue">
                            {{ row.Distance }}
                        </td>

                        <td>
                            ₹{{ row.Entry }}
                        </td>

                        <td>
                            ₹{{ row.SL }}
                        </td>

                        <td>
                            ₹{{ row.Target }}
                        </td>

                        <td>
                            ₹{{ row.High }}
                        </td>

                        <td>
                            ₹{{ row.Low }}
                        </td>

                        <td>
                            {{ row.PriceTime }}
                        </td>

                    </tr>

                    {% endfor %}

                </tbody>

            </table>

        </div>

        {% else %}

        <div class="empty">
            No waiting setups currently within 10% of entry.
        </div>

        {% endif %}

    </div>



    <div class="footer">

        FibEdge 786 • NSE Fibonacci Research Scanner

        <br>

        Yahoo Finance is currently used as the market-data source
        and may be delayed relative to the exchange.

        <br>

        Signals are generated from the 8% meaningful-swing strategy
        with 0.786 entry, 0.500 stop and 1.260 target.

        <br><br>

        Research use only. Not financial advice.

    </div>


</div>


</body>
</html>
"""


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

        dt = pd.to_datetime(value)

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

            "PriceTime":
                clean_time(
                    row.get("Price Time")
                ),

            "Status":
                row.get(
                    "Status",
                    "-"
                ),

            "High":
                clean_number(
                    row.get("High")
                ),

            "Low":
                clean_number(
                    row.get("Low")
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
                distance_text

        })

    return rows


@app.route("/")
def home():

    if not os.path.exists(
        DATA_FILE
    ):

        return """
        <body style="
            background:#07111f;
            color:white;
            font-family:Arial;
            padding:40px;
        ">
            <h2>FibEdge 786</h2>
            <p>Latest signal file not found.</p>
            <p>Run fib_price_refresh.py first.</p>
        </body>
        """


    df = pd.read_csv(
        DATA_FILE
    )


    total_count = len(df)


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


    search = (
        request.args
        .get("q", "")
        .strip()
        .upper()
    )


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

        latest_time = (
            valid_times.max()
        )

        latest_timestamp = (
            latest_time.strftime(
                "%d %b %Y • %I:%M %p"
            )
        )

    else:

        latest_timestamp = (
            "Unavailable"
        )


    return render_template_string(

        HTML,

        total_count=total_count,

        open_count=len(open_df),

        near_count=len(near_df),

        waiting_count=len(waiting_df),

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


@app.route("/refresh")
def refresh_prices():

    try:

        subprocess.run(
            [
                "python",
                REFRESH_SCRIPT
            ],
            check=True
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
                Price refresh failed
            </h2>

            <p>
                {error}
            </p>

            <a
                href="/"
                style="
                    color:#20d47b;
                "
            >
                Return to dashboard
            </a>

        </body>
        """


    return redirect(
        url_for("home")
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5005,
        debug=True
    )
