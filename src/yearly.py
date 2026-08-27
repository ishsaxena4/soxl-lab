import pandas as pd
from data import get_prices
from backtest import backtest
from strategy import vol_scaled_positions

prices = get_prices()["SOXL"]
bh = backtest(prices, pd.Series(1.0, index=prices.index))
vs = backtest(prices, vol_scaled_positions(prices).fillna(0.0))

def annual(res, col="strat_ret"):
    return res.groupby(res.index.year)[col].apply(lambda r: (1 + r).prod() - 1)

tbl = pd.DataFrame({
    "BH_ret":     annual(bh),
    "VS_ret":     annual(vs),
    "VS_meanpos": vs.groupby(vs.index.year)["position"].mean(),
})
tbl["edge"] = tbl["VS_ret"] - tbl["BH_ret"]
print(tbl.round(3))
