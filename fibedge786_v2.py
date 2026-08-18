from flask import Flask, render_template_string, redirect, url_for
import pandas as pd
import os
import subprocess

app = Flask(__name__)

CSV_FILE = "CURRENT_NSE_FIB_SETUPS.csv"
SCANNER_SCRIPT = "current_setup_scanner.py"


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
            font-family: -apple-system, BlinkMacSystemFont,
                         "Segoe UI", Roboto, Arial, sans-serif;
            background: #08111f;
            color: #e8edf5;
        }

        .topbar {
            background: #0d1726;
            border-bottom: 1px solid #1f2c3d;
            padding: 18px 24px;
            position: sticky;
            top: 0;
            z-index: 10;
        }

        .topbar-inner {
            max-width: 1200px;
            margin: auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 14px;
        }

        .brand {
            font-size: 22px;
            font-weight: 800;
            letter-spacing: 1px;
        }

        .brand span {
            color: #35d07f;
        }

        .top-actions {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .market-status {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            color: #9aa8bb;
        }

        .live-dot {
            width: 9px;
            height: 9px;
            background: #35d07f;
            border-radius: 50%;
            box-shadow: 0 0 10px #35d07f;
        }

        .refresh-button {
            background: #35d07f;
            color: #07111d;
            border: none;
            border-radius: 9px;
            padding: 10px 14px;
            font-weight: 800;
            cursor: pointer;
            text-decoration: none;
            font-size: 13px;
        }

        .container {
            max-width: 1200px;
            margin: auto;
            padding: 24px;
        }

        .hero {
            margin-bottom: 24px;
        }

        .hero h1 {
            margin: 0;
            font-size: 32px;
            font-weight: 800;
        }

        .hero p {
            color: #8492a6;
            margin-top: 8px;
        }

        .strategy {
            margin-top: 12px;
            display: inline-block;
            background: #101c2d;
            border: 1px solid #223249;
            padding: 9px 14px;
            border-radius: 8px;
            color: #9fb0c6;
            font-size: 13px;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 14px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: #0e1928;
            border: 1px solid #1d2a3d;
            border-radius: 12px;
            padding: 18px;
        }

        .stat-label {
            color: #76869b;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }

        .stat-number {
            font-size: 28px;
            font-weight: 800;
            margin-top: 6px;
        }

        .section {
            margin-bottom: 32px;
        }

        .section-title {
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 12px;
        }

        .stock-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 14px;
        }

        .stock-card {
            background: #0d1827;
            border: 1px solid #1d2b3e;
            border-radius: 14px;
            overflow: hidden;
        }

        .stock-card-header {
            padding: 16px 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #18263a;
        }

        .symbol {
            font-size: 19px;
            font-weight: 800;
        }

        .badge {
            padding: 6px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 800;
        }

        .badge-open {
            background: rgba(53, 208, 127, 0.14);
            color: #35d07f;
        }

        .badge-near {
            background: rgba(255, 193, 7, 0.14);
            color: #ffc107;
        }

        .badge-watch {
            background: rgba(80, 145, 255, 0.14);
            color: #6ea8ff;
        }

        .card-body {
            padding: 18px;
        }

        .price-label {
            color: #6f8096;
            font-size: 12px;
        }

        .price {
            font-size: 28px;
            font-weight: 800;
            margin-top: 3px;
            margin-bottom: 18px;
        }

        .levels {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
        }

        .level {
            background: #101d2e;
            border-radius: 9px;
            padding: 11px;
        }

        .level-label {
            color: #718298;
            font-size: 11px;
            margin-bottom: 5px;
        }

        .level-value {
            font-weight: 700;
            font-size: 14px;
        }

        .entry {
            color: #6ea8ff;
        }

        .sl {
            color: #ff6b6b;
        }

        .target {
            color: #35d07f;
        }

        .distance {
            margin-top: 14px;
            background: #101d2e;
            padding: 10px 12px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            font-size: 13px;
        }

        .empty {
            background: #0d1827;
            border: 1px dashed #28394f;
            border-radius: 12px;
            color: #718198;
            padding: 24px;
            text-align: center;
        }

        .footer {
            border-top: 1px solid #18263a;
            padding: 24px;
            text-align: center;
            color: #53647a;
            font-size: 12px;
            margin-top: 30px;
        }

        @media (max-width: 800px) {

            .container {
                padding: 16px;
            }

            .stats {
                grid-template-columns: repeat(2, 1fr);
            }

            .stock-grid {
                grid-template-columns: 1fr;
            }

            .topbar-inner {
                flex-direction: column;
                align-items: flex-start;
            }

        }

    </style>
</head>

<body>

<div class="topbar">

    <div class="topbar-inner">

        <div class="brand">
            FIBEDGE <span>786</span>
        </div>

        <div class="top-actions">

            <div class="market-status">
                <div class="live-dot"></div>
                Scanner Ready
            </div>

            <a class="refresh-button"
               href="{{ url_for('refresh_data') }}">
                Refresh Market Data
            </a>

        </div>

    </div>

</div>


<div class="container">

    <div class="hero">

        <h1>Market Opportunity Scanner</h1>

        <p>
            Current Fibonacci setups based on meaningful swing detection.
        </p>

        <div class="strategy">
            8% Minimum Decline ·
            15 Day Swing ·
            Entry 0.786 ·
            SL 0.500 ·
            Target 1.260
        </div>

    </div>


    <div class="stats">

        <div class="stat-card">
            <div class="stat-label">Stocks Scanned</div>
            <div class="stat-number">{{ total_scanned }}</div>
        </div>

        <div class="stat-card">
            <div class="stat-label">Open Trades</div>
            <div class="stat-number">{{ open_count }}</div>
        </div>

        <div class="stat-card">
            <div class="stat-label">Near Entry</div>
            <div class="stat-number">{{ near_count }}</div>
        </div>

        <div class="stat-card">
            <div class="stat-label">Watchlist</div>
            <div class="stat-number">{{ watch_count }}</div>
        </div>

    </div>


    <div class="section">

        <div class="section-title">
            Open Trades
        </div>

        {% if open_setups %}

        <div class="stock-grid">

            {% for stock in open_setups %}

            <div class="stock-card">

                <div class="stock-card-header">

                    <div class="symbol">
                        {{ stock.Symbol.replace(".NS", "") }}
                    </div>

                    <div class="badge badge-open">
                        OPEN
                    </div>

                </div>

                <div class="card-body">

                    <div class="price-label">
                        Current Price
                    </div>

                    <div class="price">
                        ₹{{ "%.2f"|format(stock.Price) }}
                    </div>

                    <div class="levels">

                        <div class="level">
                            <div class="level-label">
                                ENTRY 0.786
                            </div>
                            <div class="level-value entry">
                                ₹{{ "%.2f"|format(stock.Entry) }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-label">
                                STOP LOSS
                            </div>
                            <div class="level-value sl">
                                ₹{{ "%.2f"|format(stock.SL) }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-label">
                                TARGET
                            </div>
                            <div class="level-value target">
                                ₹{{ "%.2f"|format(stock.Target) }}
                            </div>
                        </div>

                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No active trades.
        </div>

        {% endif %}

    </div>


    <div class="section">

        <div class="section-title">
            Near Entry
        </div>

        {% if near_setups %}

        <div class="stock-grid">

            {% for stock in near_setups %}

            <div class="stock-card">

                <div class="stock-card-header">

                    <div class="symbol">
                        {{ stock.Symbol.replace(".NS", "") }}
                    </div>

                    <div class="badge badge-near">
                        NEAR ENTRY
                    </div>

                </div>

                <div class="card-body">

                    <div class="price-label">
                        Current Price
                    </div>

                    <div class="price">
                        ₹{{ "%.2f"|format(stock.Price) }}
                    </div>

                    <div class="levels">

                        <div class="level">
                            <div class="level-label">ENTRY</div>
                            <div class="level-value entry">
                                ₹{{ "%.2f"|format(stock.Entry) }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-label">SL</div>
                            <div class="level-value sl">
                                ₹{{ "%.2f"|format(stock.SL) }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-label">TARGET</div>
                            <div class="level-value target">
                                ₹{{ "%.2f"|format(stock.Target) }}
                            </div>
                        </div>

                    </div>

                    <div class="distance">
                        <span>Distance to Entry</span>
                        <strong>
                            {{ "%.2f"|format(stock["Distance %"]) }}%
                        </strong>
                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No stocks near entry.
        </div>

        {% endif %}

    </div>


    <div class="section">

        <div class="section-title">
            Watchlist
        </div>

        {% if watchlist %}

        <div class="stock-grid">

            {% for stock in watchlist %}

            <div class="stock-card">

                <div class="stock-card-header">

                    <div class="symbol">
                        {{ stock.Symbol.replace(".NS", "") }}
                    </div>

                    <div class="badge badge-watch">
                        WATCH
                    </div>

                </div>

                <div class="card-body">

                    <div class="price-label">
                        Current Price
                    </div>

                    <div class="price">
                        ₹{{ "%.2f"|format(stock.Price) }}
                    </div>

                    <div class="levels">

                        <div class="level">
                            <div class="level-label">ENTRY</div>
                            <div class="level-value entry">
                                ₹{{ "%.2f"|format(stock.Entry) }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-label">SL</div>
                            <div class="level-value sl">
                                ₹{{ "%.2f"|format(stock.SL) }}
                            </div>
                        </div>

                        <div class="level">
                            <div class="level-label">TARGET</div>
                            <div class="level-value target">
                                ₹{{ "%.2f"|format(stock.Target) }}
                            </div>
                        </div>

                    </div>

                    <div class="distance">
                        <span>Distance to Entry</span>
                        <strong>
                            {{ "%.2f"|format(stock["Distance %"]) }}%
                        </strong>
                    </div>

                </div>

            </div>

            {% endfor %}

        </div>

        {% else %}

        <div class="empty">
            No watchlist setups.
        </div>

        {% endif %}

    </div>

</div>


<div class="footer">
    FibEdge 786 · Fibonacci Strategy Research Dashboard
    <br><br>
    Research use only. Not financial advice.
</div>


</body>
</html>
"""


def load_data():

    if not os.path.exists(CSV_FILE):
        return None

    return pd.read_csv(CSV_FILE)


@app.route("/")
def home():

    df = load_data()

    if df is None:

        return """
        <body style="
            background:#08111f;
            color:white;
            font-family:Arial;
            padding:40px;
        ">
        <h2>Scanner data not found.</h2>
        <p>Run the scanner or refresh the market data.</p>
        </body>
        """

    open_df = df[
        df["Status"] == "OPEN"
    ].copy()

    near_df = df[
        df["Status"].isin(
            ["NEAR 0.786", "ENTRY AREA"]
        )
    ].copy()

    watch_df = df[
        (df["Status"] == "WAITING FOR 0.786")
        &
        (df["Distance %"] <= 10)
    ].copy()

    if not near_df.empty:
        near_df = near_df.sort_values("Distance %")

    if not watch_df.empty:
        watch_df = watch_df.sort_values("Distance %")

    return render_template_string(
        HTML,
        total_scanned=len(df),
        open_count=len(open_df),
        near_count=len(near_df),
        watch_count=len(watch_df),
        open_setups=open_df.to_dict("records"),
        near_setups=near_df.to_dict("records"),
        watchlist=watch_df.to_dict("records")
    )


@app.route("/refresh")
def refresh_data():

    try:

        subprocess.run(
            ["python", SCANNER_SCRIPT],
            check=True
        )

    except subprocess.CalledProcessError as error:

        return f"""
        <body style="
            background:#08111f;
            color:white;
            font-family:Arial;
            padding:40px;
        ">
        <h2>Scanner refresh failed.</h2>
        <p>{error}</p>
        </body>
        """

    return redirect(
        url_for("home")
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5002,
        debug=True
    )
