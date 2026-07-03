# =============================================================================
# china_econ_pulse/indicators.py -- 综合经济指标构建
# =============================================================================
"""
经济脉搏指数 (Pulse Index) 构建模块。
包含: 指标归一化、加权合成、趋势判定、发散检测、热力图评分。
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "indicators.yaml"


def _load_config() -> dict:
    """Load indicator configuration from YAML."""
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# PulseIndexBuilder
# ---------------------------------------------------------------------------

class PulseIndexBuilder:
    """构建中国经济脉搏指数及相关衍生指标。"""

    def __init__(self, config_path: Optional[Path] = None):
        cfg_path = config_path or _CONFIG_PATH
        with open(cfg_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.weights = self.config["pulse_weights"]
        self.thresholds = self.config["thresholds"]
        self.trend_cfg = self.config["trend_signal"]
        self.indicator_groups = self.config["indicator_groups"]
        self._indicator_meta = {item["id"]: item for item in self.config.get("indicators", [])}

    # -------------------------------------------------------------------
    # Normalization
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_zscore(series: pd.Series) -> pd.Series:
        """
        Convert a raw series to a 0-100 scale using z-score mapping.
        Maps z-score range [-3, 3] to [0, 100], clipping outliers.
        """
        mu = series.mean()
        sigma = series.std(ddof=1)
        if sigma == 0 or pd.isna(sigma):
            return pd.Series(50.0, index=series.index)
        z = (series - mu) / sigma
        # Map z in [-3, 3] to [0, 100]
        normalized = 50 + (z / 3.0) * 50
        normalized = normalized.clip(0, 100)
        return normalized

    @staticmethod
    def _normalize_minmax(series: pd.Series, low: float = 0, high: float = 100) -> pd.Series:
        """Min-max normalization to [low, high]."""
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series((low + high) / 2.0, index=series.index)
        return low + (series - mn) / (mx - mn) * (high - low)

    # -------------------------------------------------------------------
    # Extract sub-indicator series from merged DataFrame
    # -------------------------------------------------------------------

    def _extract_series(self, df: pd.DataFrame, col_name: str) -> Optional[pd.Series]:
        """Safely extract a named column as a numeric series."""
        if col_name not in df.columns:
            return None
        s = pd.to_numeric(df[col_name], errors="coerce").dropna()
        if s.empty:
            return None
        return s

    # -------------------------------------------------------------------
    # Pulse Index
    # -------------------------------------------------------------------

    def build_pulse_index(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Build the economic Pulse Index from a merged DataFrame containing all indicators.

        The Pulse Index is a weighted composite of 8 leading indicators:
          - PMI Manufacturing (20%)
          - Caixin PMI (15%)
          - Electricity growth (15%)
          - Freight growth (10%)
          - New loans (10%)
          - Consumer confidence (10%)
          - PPI YoY (10%)
          - Retail sales (10%)

        Returns DataFrame with columns: date, pulse_score, pulse_level, ...component_scores
        """
        # Map config keys to DataFrame columns
        component_map = {
            "pmi_manufacturing": "pmi_manufacturing",
            "caixin_pmi": "caixin_pmi_manufacturing",
            "electricity_growth": "electricity",
            "freight_growth": "freight_volume",
            "new_loans": "new_loans",
            "consumer_confidence": "consumer_confidence",
            "ppi_yoy": "ppi",
            "retail_sales": "retail_sales",
        }

        date_col = None
        for c in ["date", "日期"]:
            if c in merged_df.columns:
                date_col = c
                break

        if date_col is None:
            logger.error("No date column found in merged DataFrame")
            return pd.DataFrame()

        df = merged_df.copy()
        if date_col != "date":
            df = df.rename(columns={date_col: "date"})
        df["date"] = pd.to_datetime(df["date"])

        # Extract and normalize each component
        components: Dict[str, pd.Series] = {}
        for config_key, df_col in component_map.items():
            series = self._extract_series(df, df_col)
            if series is not None and len(series) > 2:
                # Align to df index
                comp_df = pd.DataFrame({"date": df["date"]})
                comp_df = comp_df.merge(
                    series.reset_index(drop=True).to_frame(df_col),
                    left_index=True, right_index=True, how="left"
                )
                # Normalize
                normalized = self._normalize_zscore(pd.Series(comp_df[df_col].values))
                components[config_key] = normalized
            else:
                logger.warning("Missing or insufficient data for: %s (column: %s)", config_key, df_col)

        if not components:
            logger.error("No valid components for Pulse Index")
            return pd.DataFrame()

        # Weighted sum
        result = pd.DataFrame({"date": df["date"].values})
        total_weight = 0.0
        pulse_raw = pd.Series(0.0, index=result.index)

        for key, w in self.weights.items():
            if key in components:
                pulse_raw = pulse_raw + components[key] * w
                total_weight += w
                result[key + "_score"] = components[key].values

        if total_weight > 0:
            pulse_raw = pulse_raw / total_weight  # renormalize if some components missing

        result["pulse_score"] = pulse_raw.values
        result["pulse_level"] = result["pulse_score"].apply(self.pulse_level)

        # Add trend
        if len(result) >= 2:
            result["pulse_change"] = result["pulse_score"].diff()
        else:
            result["pulse_change"] = 0.0
        result["trend_signal"] = result["pulse_change"].apply(self._trend_signal_label)

        # Round for display
        result["pulse_score"] = result["pulse_score"].round(1)
        result["pulse_change"] = result["pulse_change"].round(1)

        return result.sort_values("date")

    def pulse_level(self, score: float) -> str:
        """Classify pulse score into level."""
        t = self.thresholds
        if score >= t["expansion"]:
            return "expansion"
        elif score >= t["stable"]:
            return "stable"
        elif score >= t["contraction"]:
            return "contraction"
        else:
            return "warning"

    @staticmethod
    def pulse_level_cn(level: str) -> str:
        """Translate pulse level to Chinese."""
        mapping = {
            "expansion": "扩张",
            "stable": "平稳",
            "contraction": "收缩",
            "warning": "预警",
        }
        return mapping.get(level, level)

    @staticmethod
    def pulse_level_color(level: str) -> str:
        """Return color for pulse level."""
        mapping = {
            "expansion": "#C41230",   # China red
            "stable": "#F5A623",      # Amber
            "contraction": "#4A90D9",  # Blue
            "warning": "#7B7B7B",      # Gray
        }
        return mapping.get(level, "#333333")

    def trend_signal(self, pulse_history: pd.Series) -> str:
        """Determine trend from pulse history."""
        if len(pulse_history) < 2:
            return "insufficient_data"
        change = pulse_history.iloc[-1] - pulse_history.iloc[-2]
        return self._trend_signal_label(change)

    def _trend_signal_label(self, change: float) -> str:
        tc = self.trend_cfg
        if pd.isna(change):
            return "insufficient_data"
        if change >= tc["strong_up"]:
            return "strong_up"
        elif change >= tc["mild_up"]:
            return "mild_up"
        elif change > tc["mild_down"]:
            return "flat"
        elif change >= tc["mild_down"]:
            return "mild_down"
        else:
            return "strong_down"

    @staticmethod
    def trend_signal_cn(signal: str) -> str:
        mapping = {
            "strong_up": "加速上行",
            "mild_up": "温和回升",
            "flat": "横盘整理",
            "mild_down": "边际走弱",
            "strong_down": "加速下行",
            "insufficient_data": "数据不足",
        }
        return mapping.get(signal, signal)

    @staticmethod
    def trend_arrow(signal: str) -> str:
        mapping = {
            "strong_up": "↑↑",
            "mild_up": "↑",
            "flat": "→",
            "mild_down": "↓",
            "strong_down": "↓↓",
            "insufficient_data": "?",
        }
        return mapping.get(signal, "?")

    # -------------------------------------------------------------------
    # Divergence Detection
    # -------------------------------------------------------------------

    def divergence_detect(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect indicators moving in opposite directions (divergence).
        Compares the latest change direction of key indicator pairs.
        Returns DataFrame with divergence flags.
        """
        if len(merged_df) < 3:
            return pd.DataFrame()

        pairs = [
            ("pmi_manufacturing", "caixin_pmi_manufacturing", "官方PMI vs 财新PMI"),
            ("retail_sales", "consumer_confidence", "零售 vs 消费信心"),
            ("exports", "imports", "出口 vs 进口"),
            ("m1", "m2", "M1 vs M2"),
            ("new_home_prices", "floor_space_sold", "房价 vs 销售面积"),
        ]

        divergences = []
        df = merged_df.copy()
        recent = df.tail(3)

        for col_a, col_b, label in pairs:
            if col_a not in recent.columns or col_b not in recent.columns:
                continue
            a_vals = pd.to_numeric(recent[col_a], errors="coerce").dropna()
            b_vals = pd.to_numeric(recent[col_b], errors="coerce").dropna()
            if len(a_vals) < 2 or len(b_vals) < 2:
                continue
            a_dir = a_vals.iloc[-1] - a_vals.iloc[-2]
            b_dir = b_vals.iloc[-1] - b_vals.iloc[-2]

            if a_dir * b_dir < 0:  # opposite signs
                a_name = self._indicator_meta.get(col_a, {}).get("name", col_a)
                b_name = self._indicator_meta.get(col_b, {}).get("name", col_b)
                divergences.append({
                    "pair": label,
                    "indicator_a": a_name,
                    "indicator_b": b_name,
                    "a_direction": "上升" if a_dir > 0 else "下降",
                    "b_direction": "上升" if b_dir > 0 else "下降",
                    "severity": "high" if abs(a_dir) > abs(b_dir) * 2 or abs(b_dir) > abs(a_dir) * 2 else "medium",
                })

        return pd.DataFrame(divergences)

    # -------------------------------------------------------------------
    # Heat Map Scores (5 categories x 6 months)
    # -------------------------------------------------------------------

    def heat_map_scores(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate a 6 (categories) x N (months) heatmap matrix of normalized scores.
        Categories: production, demand, prices, finance, trade, property.
        """
        groups = self.indicator_groups
        if merged_df.empty:
            return pd.DataFrame()

        df = merged_df.copy()
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns:
            return pd.DataFrame()

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)
        last12 = df.tail(12)

        results = []
        for category, indicators in groups.items():
            valid_cols = [c for c in indicators if c in last12.columns]
            if not valid_cols:
                continue
            # Normalize each indicator and average
            scores = pd.Series(0.0, index=last12.index)
            for col in valid_cols:
                vals = pd.to_numeric(last12[col], errors="coerce")
                if vals.notna().sum() < 2:
                    continue
                normed = self._normalize_zscore(vals)
                scores = scores + normed.fillna(0)
            n_valid = sum(1 for c in valid_cols if pd.to_numeric(last12[c], errors="coerce").notna().sum() >= 2)
            if n_valid > 0:
                scores = scores / n_valid

            for idx_val in range(len(last12)):
                results.append({
                    "category": category,
                    "category_cn": self._category_cn(category),
                    "date": last12[date_col].iloc[idx_val],
                    "score": round(scores.iloc[idx_val], 1) if idx_val < len(scores) else np.nan,
                })

        return pd.DataFrame(results)

    @staticmethod
    def _category_cn(cat: str) -> str:
        mapping = {
            "production": "生产",
            "demand": "需求",
            "prices": "物价",
            "finance": "金融",
            "trade": "外贸",
            "property": "地产",
        }
        return mapping.get(cat, cat)

    # -------------------------------------------------------------------
    # Six-dimension Radar Scores
    # -------------------------------------------------------------------

    def radar_scores(self, merged_df: pd.DataFrame) -> Dict[str, float]:
        """
        Compute 6-dimension scores for radar chart.
        Returns dict: {production: xx, demand: xx, prices: xx, finance: xx, trade: xx, property: xx}
        Each score is 0-100.
        """
        groups = self.indicator_groups
        scores = {}

        df = merged_df.copy()
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns or df.empty:
            return {cat: 50.0 for cat in groups}

        df[date_col] = pd.to_datetime(df[date_col])
        latest = df.sort_values(date_col).tail(6)  # Use last 6 months

        for category, indicators in groups.items():
            valid_cols = [c for c in indicators if c in latest.columns]
            if not valid_cols:
                scores[category] = 50.0
                continue
            cat_vals = []
            for col in valid_cols:
                vals = pd.to_numeric(latest[col], errors="coerce").dropna()
                if len(vals) < 2:
                    continue
                # Use latest value z-scored against history
                all_vals = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(all_vals) >= 3:
                    z = (vals.iloc[-1] - all_vals.mean()) / (all_vals.std(ddof=1) or 1)
                    score = 50 + (z / 3.0) * 50
                    cat_vals.append(np.clip(score, 0, 100))
            scores[category] = round(float(np.mean(cat_vals)), 1) if cat_vals else 50.0

        return scores

    # -------------------------------------------------------------------
    # M1-M2 Scissors Gap
    # -------------------------------------------------------------------

    def m1_m2_scissors(self, merged_df: pd.DataFrame) -> Optional[pd.Series]:
        """Compute M1-M2 scissors gap (M1 YoY - M2 YoY)."""
        if "m1" not in merged_df.columns or "m2" not in merged_df.columns:
            return None
        m1 = pd.to_numeric(merged_df["m1"], errors="coerce")
        m2 = pd.to_numeric(merged_df["m2"], errors="coerce")
        return m1 - m2

    # -------------------------------------------------------------------
    # Summary stats
    # -------------------------------------------------------------------

    def summary(self, merged_df: pd.DataFrame) -> dict:
        """Generate a summary dict of latest values, changes, and signals."""
        pulse_df = self.build_pulse_index(merged_df)
        radar = self.radar_scores(merged_df)
        divergences = self.divergence_detect(merged_df)

        latest_pulse = pulse_df.iloc[-1] if not pulse_df.empty else None

        return {
            "pulse_score": float(latest_pulse["pulse_score"]) if latest_pulse is not None else None,
            "pulse_level": latest_pulse["pulse_level"] if latest_pulse is not None else None,
            "pulse_level_cn": self.pulse_level_cn(latest_pulse["pulse_level"]) if latest_pulse is not None else None,
            "trend_signal": latest_pulse["trend_signal"] if latest_pulse is not None else None,
            "trend_signal_cn": self.trend_signal_cn(latest_pulse["trend_signal"]) if latest_pulse is not None else None,
            "pulse_change": float(latest_pulse["pulse_change"]) if latest_pulse is not None else None,
            "radar": radar,
            "divergences": divergences.to_dict(orient="records") if not divergences.empty else [],
        }
