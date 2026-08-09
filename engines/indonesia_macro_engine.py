"""
Indonesia Macro Engine
=======================
Real data source connected. IDNCPIALLMINMEI (Indonesia CPI) and
IRSTCI01IDM156N (bi_rate proxy) confirmed to exist via web_search run
in an earlier session. XTNTVA01IDM664S (trade balance) confirmed via
web_search run in THIS session — previously marked "not sourced,"
now closed. usdidr and id_gdp series IDs were not independently
re-verified; treat as unconfirmed until checked live.
OECD-sourced series on FRED have historically lagged several months
behind the actual current month — do not assume "latest available"
means "last month." Verify the actual as-of date every time this runs.
Same ENVIRONMENT LIMITATION as data/fetch_macro_data.py applies:
api.stlouisfed.org is unreachable from this sandbox, so the live fetch
is untested here — only the transform math and the assessment logic
are verified (tests/test_indonesia_macro_engine.py).

Series used (FRED, OECD-sourced for Indonesia):
  - id_cpi_yoy        <- IDNCPIALLMINMEI  (Indonesia CPI, monthly index)
  - bi_rate           <- IRSTCI01IDM156N  (Indonesia interbank/call money
                          rate, monthly % — a proxy, not the official BI
                          7-Day Reverse Repo Rate; FRED does not carry
                          BI's exact policy rate as a clean auto-updating
                          series. Tracks it closely but can diverge
                          during liquidity stress. Flagged, not hidden.)
  - usdidr            <- CCUSMA02IDQ618N  (USD/IDR, QUARTERLY only — the
                          only reliable free auto-updating source found.
                          Monthly would need a paid FX provider or
                          scraping BI's JISDOR rate — deliberately out
                          of scope, see design decision below.)
  - id_gdp_yoy        <- NGDPRSAXDCIDQ    (Real GDP, quarterly, SA)
  - id_trade_balance  <- XTNTVA01IDM664S  (Trade balance, monthly,
                          Rupiah, seasonally adjusted — OECD via FRED)

FINAL DESIGN DECISION (not a placeholder — this is the intended
permanent shape of this capability):
Unlike the global regime engine, this deliberately does NOT attempt
its own KMeans regime clustering for Indonesia. Building and
validating a proper Indonesia-specific regime model would need years
of historical ID data run through the same rigor as the global model
(backtesting, centroid validation, sample-size adequacy per cluster)
— a substantial, separate modeling project with its own data
requirements, not a "smallest new module" addition, and not something
that should be improvised without that rigor. A fabricated regime
label that looks equivalent to the global engine but isn't validated
would be worse than an honest, lighter-weight tool. This engine
therefore permanently produces a rule-based directional assessment
(inflation rising/falling, rate hiking/cutting, IDR strengthening/
weakening, trade balance widening/narrowing) — simpler than the
global engine, explicitly and permanently so, not a step on the way
to becoming one. If ID-specific regime classification is wanted in
the future, it is new scope requiring new data collection, not an
extension of this file.
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import INDONESIA_FEATURES_TARGET

ID_FRED_SERIES = {
    "id_cpi":            "IDNCPIALLMINMEI",
    "bi_rate":           "IRSTCI01IDM156N",
    "usdidr":            "CCUSMA02IDQ618N",   # quarterly
    "id_gdp":            "NGDPRSAXDCIDQ",     # quarterly
    "id_trade_balance":  "XTNTVA01IDM664S",   # monthly, Rupiah, SA
}
LOOKBACK_DAYS = 900


class IndonesiaMacroEngine:
    IMPLEMENTED = True
    NOT_SOURCED = []  # was ["id_trade_balance"] — closed this session, see docstring

    def fetch_raw(self, fred_api_key: str) -> dict:
        from data.fetch_macro_data import fetch_fred_series  # reuse, don't duplicate
        return {key: fetch_fred_series(series_id, fred_api_key, LOOKBACK_DAYS)
                for key, series_id in ID_FRED_SERIES.items()}

    def assess(self, raw: dict) -> dict:
        """
        Rule-based directional read, not a regime classification —
        see the FINAL DESIGN DECISION in the module docstring for why
        that's permanent, not a gap.
        raw: dict of monthly pd.Series keyed like ID_FRED_SERIES.
        """
        cpi = raw["id_cpi"]
        bi = raw["bi_rate"]
        fx = raw["usdidr"].resample("ME").ffill()  # quarterly -> forward-filled monthly view
        gdp = raw["id_gdp"].resample("ME").ffill()
        trade = raw.get("id_trade_balance")

        id_cpi_yoy = (cpi.iloc[-1] / cpi.iloc[-13] - 1) * 100 if len(cpi) >= 13 else np.nan
        bi_rate_level = float(bi.iloc[-1])
        bi_rate_3m_change = float(bi.iloc[-1] - bi.iloc[-4]) if len(bi) >= 4 else np.nan
        usdidr_level = float(fx.dropna().iloc[-1]) if fx.dropna().shape[0] else np.nan
        usdidr_3m_change_pct = (
            (fx.dropna().iloc[-1] / fx.dropna().iloc[-4] - 1) * 100
            if fx.dropna().shape[0] >= 4 else np.nan
        )
        id_gdp_yoy = (
            (gdp.dropna().iloc[-1] / gdp.dropna().iloc[-13] - 1) * 100
            if gdp.dropna().shape[0] >= 13 else np.nan
        )
        trade_balance_level = float(trade.iloc[-1]) if trade is not None and len(trade) else np.nan
        trade_balance_3m_change_pct = (
            (trade.iloc[-1] / abs(trade.iloc[-4]) - 1) * 100
            if trade is not None and len(trade) >= 4 and trade.iloc[-4] != 0 else np.nan
        )

        inflation_direction = "rising" if id_cpi_yoy > 4.0 else ("elevated but stable" if id_cpi_yoy > 3.0 else "contained")
        policy_stance = "hiking" if bi_rate_3m_change > 0.1 else ("cutting" if bi_rate_3m_change < -0.1 else "holding")
        idr_direction = "weakening" if usdidr_3m_change_pct > 1.0 else ("strengthening" if usdidr_3m_change_pct < -1.0 else "stable")
        trade_direction = (
            "unknown" if np.isnan(trade_balance_level)
            else "widening surplus" if not np.isnan(trade_balance_3m_change_pct) and trade_balance_level > 0 and trade_balance_3m_change_pct > 5
            else "narrowing surplus" if not np.isnan(trade_balance_3m_change_pct) and trade_balance_level > 0 and trade_balance_3m_change_pct < -5
            else "deficit" if trade_balance_level < 0
            else "stable"
        )

        return {
            "id_cpi_yoy_pct": round(float(id_cpi_yoy), 2),
            "inflation_read": inflation_direction,
            "bi_rate_proxy_pct": round(bi_rate_level, 2),
            "policy_stance": policy_stance,
            "usdidr_level": round(usdidr_level, 0),
            "idr_direction_3m": idr_direction,
            "id_gdp_yoy_pct": round(float(id_gdp_yoy), 2) if not np.isnan(id_gdp_yoy) else None,
            "trade_balance_rupiah": round(trade_balance_level, 0) if not np.isnan(trade_balance_level) else None,
            "trade_balance_read": trade_direction,
            "not_sourced": self.NOT_SOURCED,
            "caveats": [
                "bi_rate is an interbank-rate proxy, not the official BI 7-Day Reverse Repo Rate",
                "usdidr is quarterly data forward-filled to monthly — not a real monthly read",
                "This is a rule-based directional read, not a validated regime classification like the global engine — a permanent design decision, not a gap (see module docstring)",
            ],
        }

    def status(self) -> dict:
        return {
            "implemented": self.IMPLEMENTED,
            "target_schema": INDONESIA_FEATURES_TARGET,
            "not_sourced": self.NOT_SOURCED,
            "note": "Live fetch untested in this sandbox — api.stlouisfed.org not reachable here. See module docstring.",
        }


if __name__ == "__main__":
    import json
    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        print(json.dumps(IndonesiaMacroEngine().status(), indent=2))
    else:
        engine = IndonesiaMacroEngine()
        raw = engine.fetch_raw(api_key)
        print(json.dumps(engine.assess(raw), indent=2, default=str))
