import yfinance as yf
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from flask import Flask, request

app = Flask(__name__)

POSITIVE_WORDS = [
    "beat", "beats", "surge", "surges", "soar", "soars", "rally", "rallies",
    "gain", "gains", "growth", "profit", "profits", "upgrade", "upgraded",
    "outperform", "record", "strong", "bullish", "jump", "jumps", "rise", "rises",
    "boost", "boosts", "expand", "expands", "positive", "buy", "raises", "raised"
]
NEGATIVE_WORDS = [
    "miss", "misses", "plunge", "plunges", "slump", "slumps", "fall", "falls",
    "loss", "losses", "downgrade", "downgraded", "underperform", "weak",
    "bearish", "drop", "drops", "decline", "declines", "cut", "cuts", "layoff",
    "layoffs", "lawsuit", "recall", "warning", "sell", "negative", "concern", "concerns"
]


def score_headline(title):
    title_lower = title.lower()
    pos_hits = sum(1 for w in POSITIVE_WORDS if w in title_lower)
    neg_hits = sum(1 for w in NEGATIVE_WORDS if w in title_lower)
    if pos_hits > neg_hits:
        return "positive"
    elif neg_hits > pos_hits:
        return "negative"
    return "neutral"


def get_news_sentiment(ticker):
    try:
        stock = yf.Ticker(ticker)
        news_items = stock.news[:10]
    except Exception:
        return [], "neutral"

    scored = []
    for item in news_items:
        content = item.get("content", item)
        title = content.get("title") if isinstance(content, dict) else None
        if not title:
            title = item.get("title", "")
        if not title:
            continue
        sentiment = score_headline(title)
        scored.append({"title": title, "sentiment": sentiment})

    if not scored:
        return [], "neutral"

    pos = sum(1 for s in scored if s["sentiment"] == "positive")
    neg = sum(1 for s in scored if s["sentiment"] == "negative")
    if pos > neg:
        overall = "positive"
    elif neg > pos:
        overall = "negative"
    else:
        overall = "neutral"

    return scored, overall


def calculate_rsi(close_prices, period=14):
    delta = close_prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


@app.route("/")
def chart():
    ticker = request.args.get("ticker", "AAPL").upper()

    search_box = """
        <form method="get" style="padding:16px; font-family:sans-serif;">
            <input type="text" name="ticker" placeholder="Enter ticker e.g. TSLA"
                   style="padding:8px; font-size:16px; width:220px;">
            <button type="submit" style="padding:8px 16px; font-size:16px;">Search</button>
        </form>
    """

    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period="6mo")

        if data.empty:
            body = search_box + f"<p style='color:white; font-family:sans-serif; padding:0 16px;'>No data found for '{ticker}'. Check the ticker symbol and try again.</p>"
            return "<html><body style='background-color:#111; margin:0;'>" + body + "</body></html>"

        data["MA20"] = data["Close"].rolling(window=20).mean()
        data["MA50"] = data["Close"].rolling(window=50).mean()
        data["RSI"] = calculate_rsi(data["Close"])
        latest = data.iloc[-1]

        technical_signals = []
        technical_lean = 0
        if pd.notna(latest["MA20"]) and pd.notna(latest["MA50"]):
            if latest["MA20"] > latest["MA50"]:
                technical_signals.append("short-term trend is above the longer-term trend (bullish lean)")
                technical_lean += 1
            else:
                technical_signals.append("short-term trend is below the longer-term trend (bearish lean)")
                technical_lean -= 1

        if pd.notna(latest["RSI"]):
            if latest["RSI"] > 70:
                technical_signals.append(f"RSI is {latest['RSI']:.0f} (overbought territory)")
                technical_lean -= 1
            elif latest["RSI"] < 30:
                technical_signals.append(f"RSI is {latest['RSI']:.0f} (oversold territory)")
                technical_lean += 1
            else:
                technical_signals.append(f"RSI is {latest['RSI']:.0f} (neutral)")

        news_items, news_overall = get_news_sentiment(ticker)
        news_lean = {"positive": 1, "negative": -1, "neutral": 0}[news_overall]

        total_lean = technical_lean + news_lean
        if total_lean > 0:
            overall_read = "Leaning UP"
            overall_color = "#3ecf6e"
        elif total_lean < 0:
            overall_read = "Leaning DOWN"
            overall_color = "#e0524d"
        else:
            overall_read = "Mixed / Neutral"
            overall_color = "#cccccc"

        summary_text = f"{ticker}: " + "; ".join(technical_signals)
        summary_text += f"; recent news sentiment is {news_overall}"

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.75, 0.25], vertical_spacing=0.03,
            subplot_titles=(f"{ticker} - Last 6 Months", "RSI")
        )
        fig.add_trace(go.Candlestick(
            x=data.index, open=data["Open"], high=data["High"],
            low=data["Low"], close=data["Close"], name=ticker
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["MA20"], line=dict(width=1.5, color="#f5a623"), name="20-day MA"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["MA50"], line=dict(width=1.5, color="#4a90d9"), name="50-day MA"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=data.index, y=data["RSI"], line=dict(width=1.5, color="#bd10e0"), name="RSI"
        ), row=2, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="gray", row=2, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="gray", row=2, col=1)
        fig.update_layout(
            xaxis_rangeslider_visible=False, template="plotly_dark",
            height=750, margin=dict(t=60, b=20)
        )
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
        chart_html = fig.to_html(full_html=False)

        sentiment_colors = {"positive": "#3ecf6e", "negative": "#e0524d", "neutral": "#999"}
        news_rows = ""
        for n in news_items:
            color = sentiment_colors[n["sentiment"]]
            news_rows += f"""
                <div style="padding:6px 0; border-bottom:1px solid #222;">
                    <span style="color:{color}; font-weight:bold; text-transform:uppercase; font-size:11px;">{n['sentiment']}</span>
                    <span style="color:#ddd; margin-left:8px;">{n['title']}</span>
                </div>
            """
        if not news_rows:
            news_rows = "<p style='color:#777;'>No recent news found for this ticker.</p>"

        summary_html = f"""
            <div style="padding:0 16px; font-family:sans-serif;">
                <div style="font-size:20px; font-weight:bold; color:{overall_color}; margin-bottom:6px;">
                    Overall read: {overall_read}
                </div>
                <div style="color:#ccc; font-size:15px;">{summary_text}</div>
                <div style="font-size:12px; color:#777; margin-top:4px;">
                    Rule-based read of technicals + recent headline tone only — not financial advice or a real prediction.
                </div>
            </div>
        """

        news_html = f"""
            <div style="padding:16px; font-family:sans-serif; max-width:900px;">
                <div style="font-size:16px; color:#ddd; margin-bottom:8px; font-weight:bold;">Recent headlines</div>
                {news_rows}
            </div>
        """

        page = "<html><head><title>" + ticker + " Chart</title></head>"
        page += "<body style='background-color:#111; margin:0;'>"
        page += search_box
        page += summary_html
        page += chart_html
        page += news_html
        page += "</body></html>"
        return page

    except Exception as e:
        body = search_box + f"<p style='color:white; font-family:sans-serif; padding:0 16px;'>Something went wrong looking up '{ticker}': {e}</p>"
        return "<html><body style='background-color:#111; margin:0;'>" + body + "</body></html>"


if __name__ == "__main__":
    app.run(debug=True, port=5001)