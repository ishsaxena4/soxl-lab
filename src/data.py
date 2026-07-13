import yfinance as yf
import pandas as pd


def get_prices(tickers=("SOXL", "SOXS", "SOXX"), start="2015-01-01"):
    """
    Download daily closing prices, split/dividend-adjusted (auto_adjust=True).
    Returns a DataFrame indexed by date, one column per ticker.
    """
    data = yf.download(list(tickers), start=start, auto_adjust=True)["Close"].dropna()
    return data


if __name__ == "__main__":
    data = get_prices()

    # Daily simple returns: (price_today / price_yesterday) - 1
    rets = data.pct_change().dropna()

    # --- The real measurement: actual leveraged return vs the naive "Nx" assumption ---
    # A naive investor assumes SOXL delivers 3x the index's return OVER ANY PERIOD.
    # Let's test that year by year.
    def period_return(df):
        return (1 + df).prod() - 1          # compound the daily returns

    yearly = rets.groupby(rets.index.year).apply(period_return)
    yearly["3x_SOXX"]  = 3 * yearly["SOXX"]          # what naive 3x would give
    yearly["gap_SOXL"] = yearly["SOXL"] - yearly["3x_SOXX"]  # actual minus naive

    print(yearly[["SOXX", "SOXL", "3x_SOXX", "gap_SOXL"]].round(3))
