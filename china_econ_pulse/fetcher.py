# =============================================================================
# china_econ_pulse/fetcher.py -- akshare 数据抓取模块
# =============================================================================
"""
中国宏观经济数据抓取器，基于 akshare 库。
所有函数内置重试机制和 30 天 JSON 缓存，返回 pandas DataFrame。
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 缓存基础设施
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(__file__).resolve().parent.parent / "output" / ".cache"
_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 days


def _cache_path(key: str) -> Path:
    """Generate a cache file path for a given key."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = key.replace("/", "_").replace("\\", "_")
    return _CACHE_DIR / f"{safe_key}.json"


def _cache_get(key: str) -> Optional[pd.DataFrame]:
    """Retrieve cached DataFrame if still fresh."""
    cp = _cache_path(key)
    if not cp.exists():
        return None
    age = time.time() - cp.stat().st_mtime
    if age > _CACHE_TTL_SECONDS:
        return None
    try:
        with open(cp, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        if "date" in df.columns or "日期" in df.columns:
            date_col = "date" if "date" in df.columns else "日期"
            df[date_col] = pd.to_datetime(df[date_col])
        return df
    except Exception:
        return None


def _cache_set(key: str, df: pd.DataFrame) -> None:
    """Save DataFrame to cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = _cache_path(key)
    # Convert datetime columns to strings for JSON serialization
    export = df.copy()
    for col in export.columns:
        if pd.api.types.is_datetime64_any_dtype(export[col]):
            export[col] = export[col].dt.strftime("%Y-%m-%d")
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(export.to_dict(orient="records"), f, ensure_ascii=False, default=str)


def _retry(func, max_retries=3, delay=2.0, backoff=2.0):
    """Decorator-like wrapper for retry logic."""
    last_exc = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_exc = e
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt + 1, max_retries, func.__name__, e
            )
            if attempt < max_retries - 1:
                time.sleep(delay * (backoff ** attempt))
    raise last_exc


# ---------------------------------------------------------------------------
# DataFetcher 类
# ---------------------------------------------------------------------------

class DataFetcher:
    """中国经济数据抓取器，封装所有 akshare 调用。"""

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._ensure_akshare()

    @staticmethod
    def _ensure_akshare():
        try:
            import akshare as ak
            return ak
        except ImportError:
            raise ImportError(
                "akshare is required. Install with: pip install akshare"
            )

    def _cached_fetch(self, key: str, fetch_fn, force_refresh: bool = False):
        """Generic cached fetch wrapper."""
        if self.use_cache and not force_refresh:
            cached = _cache_get(key)
            if cached is not None and not cached.empty:
                logger.info("Using cached data for: %s", key)
                return cached
        logger.info("Fetching fresh data for: %s", key)
        df = _retry(fetch_fn)
        if self.use_cache and df is not None and not df.empty:
            _cache_set(key, df)
        return df

    # -----------------------------------------------------------------------
    # PMI
    # -----------------------------------------------------------------------

    def fetch_pmi(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch manufacturing and non-manufacturing PMI from akshare.
        Returns DataFrame with columns: date, pmi_manufacturing, pmi_non_manufacturing
        """
        def _fetch():
            ak = self._ensure_akshare()
            df = ak.macro_china_pmi()
            # akshare PMI returns columns: 日期, 制造业, 非制造业
            # Rename for consistency
            col_map = {
                "日期": "date",
                "制造业": "pmi_manufacturing",
                "非制造业": "pmi_non_manufacturing",
            }
            # Also handle English column names
            col_map_en = {
                "date": "date",
                "manufacturing": "pmi_manufacturing",
                "non_manufacturing": "pmi_non_manufacturing",
            }
            df = df.rename(columns=col_map)
            # Fallback: check if English columns present
            for old, new in col_map_en.items():
                if old in df.columns:
                    df = df.rename(columns={old: new})
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            return df

        return self._cached_fetch("pmi", _fetch, force_refresh)

    def fetch_caixin_pmi(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch Caixin manufacturing and services PMI.
        Returns DataFrame with columns: date, caixin_pmi_manufacturing, caixin_pmi_services
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df_mfg = ak.macro_china_caixin_manufacturing_pmi()
                df_mfg = df_mfg.rename(columns={"日期": "date", "制造业PMI": "caixin_pmi_manufacturing"})
                if "date" in df_mfg.columns:
                    df_mfg["date"] = pd.to_datetime(df_mfg["date"])
            except Exception:
                df_mfg = pd.DataFrame(columns=["date", "caixin_pmi_manufacturing"])

            try:
                df_svc = ak.macro_china_caixin_services_pmi()
                df_svc = df_svc.rename(columns={"日期": "date", "服务业PMI": "caixin_pmi_services"})
                if "date" in df_svc.columns:
                    df_svc["date"] = pd.to_datetime(df_svc["date"])
            except Exception:
                df_svc = pd.DataFrame(columns=["date", "caixin_pmi_services"])

            if not df_mfg.empty and not df_svc.empty:
                df = pd.merge(df_mfg, df_svc, on="date", how="outer")
            elif not df_mfg.empty:
                df = df_mfg
            elif not df_svc.empty:
                df = df_svc
            else:
                logger.warning("Caixin PMI data not available via akshare; returning empty DataFrame")
                df = pd.DataFrame(columns=["date", "caixin_pmi_manufacturing", "caixin_pmi_services"])

            if "date" in df.columns and not df.empty:
                df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date") if "date" in df.columns and not df.empty else df

        return self._cached_fetch("caixin_pmi", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # CPI / PPI
    # -----------------------------------------------------------------------

    def fetch_cpi_ppi(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch CPI and PPI YoY data.
        Returns DataFrame with columns: date, cpi, ppi
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_cpi_yoy()
                # Expected columns: 日期, 全国
                df = df.rename(columns={"日期": "date", "全国": "cpi"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                # Get PPI
                df_ppi = ak.macro_china_ppi_yoy()
                df_ppi = df_ppi.rename(columns={"日期": "date", "全国": "ppi"})
                if "date" in df_ppi.columns:
                    df_ppi["date"] = pd.to_datetime(df_ppi["date"])
                df = pd.merge(df, df_ppi, on="date", how="outer")
                return df.sort_values("date")
            except Exception:
                # Fallback: try single CPI
                pass
            try:
                df = ak.macro_china_cpi_monthly()
                col_map = {"日期": "date"}
                if "全国-当月" in df.columns:
                    col_map["全国-当月"] = "cpi"
                elif "cpi" in df.columns:
                    col_map["cpi"] = "cpi"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch CPI/PPI: %s", e)
                return pd.DataFrame(columns=["date", "cpi", "ppi"])

        return self._cached_fetch("cpi_ppi", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Industrial Production
    # -----------------------------------------------------------------------

    def fetch_industrial_production(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch industrial value-added YoY growth.
        Returns DataFrame with columns: date, industrial_production
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_industrial_production_yoy()
                col_map = {"日期": "date"}
                # Find the YoY column
                for c in df.columns:
                    if "同比" in c or "yoy" in c.lower() or "growth" in c.lower():
                        col_map[c] = "industrial_production"
                        break
                if "industrial_production" not in col_map.values() and len(df.columns) >= 2:
                    col_map[df.columns[1]] = "industrial_production"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch industrial production: %s", e)
                return pd.DataFrame(columns=["date", "industrial_production"])

        return self._cached_fetch("industrial_production", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Fixed Asset Investment
    # -----------------------------------------------------------------------

    def fetch_fixed_asset_investment(self, force_refresh: bool = False) -> pd.DataFrame:
        """Returns DataFrame with columns: date, fixed_asset_investment"""
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_fixed_asset_investment_yoy()
                col_map = {"日期": "date"}
                for c in df.columns:
                    if "同比" in c or "累计" in c or "growth" in c.lower():
                        col_map[c] = "fixed_asset_investment"
                        break
                if "fixed_asset_investment" not in col_map.values() and len(df.columns) >= 2:
                    col_map[df.columns[1]] = "fixed_asset_investment"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch FAI: %s", e)
                return pd.DataFrame(columns=["date", "fixed_asset_investment"])

        return self._cached_fetch("fixed_asset_investment", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Retail Sales
    # -----------------------------------------------------------------------

    def fetch_retail_sales(self, force_refresh: bool = False) -> pd.DataFrame:
        """Returns DataFrame with columns: date, retail_sales"""
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_consumer_goods_retail_yoy()
                col_map = {"日期": "date"}
                for c in df.columns:
                    if "同比" in c or "yoy" in c.lower() or "growth" in c.lower():
                        col_map[c] = "retail_sales"
                        break
                if "retail_sales" not in col_map.values() and len(df.columns) >= 2:
                    col_map[df.columns[1]] = "retail_sales"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch retail sales: %s", e)
                return pd.DataFrame(columns=["date", "retail_sales"])

        return self._cached_fetch("retail_sales", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Trade Data
    # -----------------------------------------------------------------------

    def fetch_trade_data(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch exports, imports, trade balance.
        Returns DataFrame with columns: date, exports, imports, trade_balance
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_trade_balance()
                col_map = {"日期": "date"}
                for c in df.columns:
                    if "出口" in c:
                        col_map[c] = "exports"
                    elif "进口" in c:
                        col_map[c] = "imports"
                    elif "差额" in c or "贸易差额" in c:
                        col_map[c] = "trade_balance"
                if "trade_balance" not in col_map.values() and "exports" in col_map.values() and "imports" in col_map.values():
                    pass  # will compute below
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                # Compute trade_balance if not present
                if "trade_balance" not in df.columns and "exports" in df.columns and "imports" in df.columns:
                    df["trade_balance"] = pd.to_numeric(df["exports"], errors="coerce") - pd.to_numeric(df["imports"], errors="coerce")
                return df.sort_values("date") if "date" in df.columns else df
            except Exception as e:
                logger.error("Failed to fetch trade data: %s", e)
                return pd.DataFrame(columns=["date", "exports", "imports", "trade_balance"])

        return self._cached_fetch("trade_data", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Money Supply (M0, M1, M2)
    # -----------------------------------------------------------------------

    def fetch_money_supply(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch M0, M1, M2 YoY growth.
        Returns DataFrame with columns: date, m0, m1, m2
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_money_supply()
                # akshare returns columns like: 月份, M2同比, M1同比, M0同比, ...
                col_map = {"月份": "date"}
                for c in df.columns:
                    if "M0" in c.upper() or "m0" in c.lower():
                        col_map[c] = "m0"
                    elif "M1" in c.upper() or "m1" in c.lower():
                        col_map[c] = "m1"
                    elif "M2" in c.upper() or "m2" in c.lower():
                        col_map[c] = "m2"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df.sort_values("date") if "date" in df.columns and not df.empty else df
            except Exception as e:
                logger.error("Failed to fetch money supply: %s", e)
                return pd.DataFrame(columns=["date", "m0", "m1", "m2"])

        return self._cached_fetch("money_supply", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Social Financing & New Loans
    # -----------------------------------------------------------------------

    def fetch_social_financing(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch total social financing and new RMB loans.
        Returns DataFrame with columns: date, social_financing, new_loans
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_shrzgm()
                col_map = {"月份": "date"}
                for c in df.columns:
                    if "社会融资规模" in c:
                        col_map[c] = "social_financing"
                    elif "新增人民币贷款" in c or "人民币贷款" in c:
                        col_map[c] = "new_loans"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df.sort_values("date") if "date" in df.columns and not df.empty else df
            except Exception as e:
                logger.error("Failed to fetch social financing: %s", e)
                return pd.DataFrame(columns=["date", "social_financing", "new_loans"])

        return self._cached_fetch("social_financing", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Electricity Consumption
    # -----------------------------------------------------------------------

    def fetch_electricity(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch electricity consumption as proxy for real economic activity.
        Returns DataFrame with columns: date, electricity
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_electricity()
                col_map = {"日期": "date"}
                # Find the YoY or total column
                for c in df.columns:
                    if "同比" in c or "yoy" in c.lower() or "全社会" in c:
                        col_map[c] = "electricity"
                        break
                if "electricity" not in col_map.values() and len(df.columns) >= 2:
                    col_map[df.columns[1]] = "electricity"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch electricity data: %s", e)
                return pd.DataFrame(columns=["date", "electricity"])

        return self._cached_fetch("electricity", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Freight Volume
    # -----------------------------------------------------------------------

    def fetch_freight_volume(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch freight volume (logistics proxy).
        Returns DataFrame with columns: date, freight_volume
        """
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_freight_volume()
                col_map = {"日期": "date"}
                for c in df.columns:
                    if "货运" in c or "yoy" in c.lower() or "同比" in c:
                        col_map[c] = "freight_volume"
                        break
                if "freight_volume" not in col_map.values() and len(df.columns) >= 2:
                    col_map[df.columns[1]] = "freight_volume"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch freight volume: %s", e)
                return pd.DataFrame(columns=["date", "freight_volume"])

        return self._cached_fetch("freight_volume", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Property Market
    # -----------------------------------------------------------------------

    def fetch_property_market(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Fetch real estate market indicators.
        Returns DataFrame with columns: date, new_home_prices, floor_space_sold, real_estate_investment
        """
        def _fetch():
            ak = self._ensure_akshare()
            # We'll try multiple sources
            result_dfs = []

            # 1. New home price index
            try:
                df_price = ak.macro_china_new_house_price()
                col_map = {"日期": "date"}
                for c in df_price.columns:
                    if "环比" in c or "新" in c or "price" in c.lower() or "index" in c.lower():
                        col_map[c] = "new_home_prices"
                        break
                if "new_home_prices" not in col_map.values() and len(df_price.columns) >= 2:
                    col_map[df_price.columns[1]] = "new_home_prices"
                df_price = df_price.rename(columns={k: v for k, v in col_map.items() if k in df_price.columns})
                if "date" in df_price.columns:
                    df_price["date"] = pd.to_datetime(df_price["date"])
                result_dfs.append(df_price[["date", "new_home_prices"]])
            except Exception as e:
                logger.warning("Could not fetch new home prices: %s", e)

            # 2. Floor space sold
            try:
                df_area = ak.macro_china_real_estate_sale()
                col_map = {"日期": "date"}
                for c in df_area.columns:
                    if "面积" in c or "销售" in c:
                        col_map[c] = "floor_space_sold"
                        break
                if "floor_space_sold" not in col_map.values() and len(df_area.columns) >= 2:
                    col_map[df_area.columns[1]] = "floor_space_sold"
                df_area = df_area.rename(columns={k: v for k, v in col_map.items() if k in df_area.columns})
                if "date" in df_area.columns:
                    df_area["date"] = pd.to_datetime(df_area["date"])
                result_dfs.append(df_area[["date", "floor_space_sold"]])
            except Exception as e:
                logger.warning("Could not fetch real estate sale area: %s", e)

            # 3. Real estate investment
            try:
                df_inv = ak.macro_china_real_estate_investment()
                col_map = {"日期": "date"}
                for c in df_inv.columns:
                    if "投资" in c or "同比" in c or "growth" in c.lower():
                        col_map[c] = "real_estate_investment"
                        break
                if "real_estate_investment" not in col_map.values() and len(df_inv.columns) >= 2:
                    col_map[df_inv.columns[1]] = "real_estate_investment"
                df_inv = df_inv.rename(columns={k: v for k, v in col_map.items() if k in df_inv.columns})
                if "date" in df_inv.columns:
                    df_inv["date"] = pd.to_datetime(df_inv["date"])
                result_dfs.append(df_inv[["date", "real_estate_investment"]])
            except Exception as e:
                logger.warning("Could not fetch real estate investment: %s", e)

            if not result_dfs:
                return pd.DataFrame(columns=["date", "new_home_prices", "floor_space_sold", "real_estate_investment"])

            # Merge all property data
            df = result_dfs[0]
            for extra in result_dfs[1:]:
                df = pd.merge(df, extra, on="date", how="outer")
            return df.sort_values("date") if "date" in df.columns else df

        return self._cached_fetch("property_market", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Consumer Confidence
    # -----------------------------------------------------------------------

    def fetch_consumer_confidence(self, force_refresh: bool = False) -> pd.DataFrame:
        """Returns DataFrame with columns: date, consumer_confidence"""
        def _fetch():
            ak = self._ensure_akshare()
            try:
                df = ak.macro_china_consumer_confidence_index()
                col_map = {"日期": "date"}
                for c in df.columns:
                    if "信心" in c or "confidence" in c.lower() or "指数" in c:
                        col_map[c] = "consumer_confidence"
                        break
                if "consumer_confidence" not in col_map.values() and len(df.columns) >= 2:
                    col_map[df.columns[1]] = "consumer_confidence"
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                return df
            except Exception as e:
                logger.error("Failed to fetch consumer confidence: %s", e)
                return pd.DataFrame(columns=["date", "consumer_confidence"])

        return self._cached_fetch("consumer_confidence", _fetch, force_refresh)

    # -----------------------------------------------------------------------
    # Bulk fetch -- get everything at once
    # -----------------------------------------------------------------------

    def fetch_all(self, force_refresh: bool = False) -> Dict[str, pd.DataFrame]:
        """
        Fetch all indicators and return a dictionary of DataFrames.
        Keys match the indicator IDs in config/indicators.yaml.
        """
        logger.info("Fetching all economic indicators...")
        results = {}

        fetch_map = {
            "pmi": self.fetch_pmi,
            "caixin_pmi": self.fetch_caixin_pmi,
            "cpi_ppi": self.fetch_cpi_ppi,
            "industrial_production": self.fetch_industrial_production,
            "fixed_asset_investment": self.fetch_fixed_asset_investment,
            "retail_sales": self.fetch_retail_sales,
            "trade_data": self.fetch_trade_data,
            "money_supply": self.fetch_money_supply,
            "social_financing": self.fetch_social_financing,
            "electricity": self.fetch_electricity,
            "freight_volume": self.fetch_freight_volume,
            "property_market": self.fetch_property_market,
            "consumer_confidence": self.fetch_consumer_confidence,
        }

        for key, fn in fetch_map.items():
            try:
                results[key] = fn(force_refresh)
                logger.info("  Fetched %s: %d rows", key, len(results[key]))
            except Exception as e:
                logger.error("  Failed %s: %s", key, e)
                results[key] = pd.DataFrame()

        return results
