
import yfinance as yf

# Change this to any stock ticker you like, e.g. "TSLA", "MSFT"
ticker = "AAPL"

stock = yf.Ticker(ticker)
data = stock.history(period="5d")

print(f"Last 5 days of {ticker} price data:")
print(data[["Open", "High", "Low", "Close", "Volume"]])