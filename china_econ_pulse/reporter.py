# =============================================================================
# china_econ_pulse/reporter.py -- HTML 报告生成器
# =============================================================================
"""
自包含 HTML 报告生成器。
产出单一 .html 文件，所有 CSS/JS/Plotly 内联，可离线浏览。
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.io as pio
from jinja2 import Template

from .indicators import PulseIndexBuilder
from .viz import Visualizer, CHINA_RED, ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_GRAY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>中国经济脉搏报告 | China Econ Pulse</title>
    {{ plotly_js }}
    <style>
        /* ===== RESET & BASE ===== */
        *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
        :root{
            --red:#C41230;--red-light:#E8553D;--blue:#4A90D9;--green:#27AE60;
            --amber:#F5A623;--gray:#7B7B7B;--dark:#2D2D2D;--muted:#6B7280;
            --bg:#F5F5F5;--card:#FFFFFF;--border:#E5E7EB;--shadow:0 1px 3px rgba(0,0,0,.08);
            --radius:10px;
        }
        body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei","PingFang SC",sans-serif;background:var(--bg);color:var(--dark);line-height:1.6}
        a{color:var(--red);text-decoration:none}

        /* ===== LAYOUT ===== */
        .container{max-width:1280px;margin:0 auto;padding:0 24px}
        .section{margin:32px 0}

        /* ===== COVER / HERO ===== */
        .hero{background:linear-gradient(135deg,var(--red) 0%,#8B0000 100%);color:#fff;padding:48px 0 40px;text-align:center}
        .hero .container{max-width:960px}
        .hero .badge{display:inline-block;background:rgba(255,255,255,.18);color:#fff;padding:4px 16px;border-radius:100px;font-size:13px;font-weight:500;margin-bottom:16px;letter-spacing:.5px}
        .hero h1{font-size:40px;font-weight:800;letter-spacing:-0.5px;margin-bottom:8px}
        .hero .subtitle{font-size:16px;opacity:.85;margin-bottom:28px}
        .hero .meta{font-size:13px;opacity:.7;margin-top:12px}
        .pulse-big{display:inline-flex;align-items:baseline;gap:12px}
        .pulse-big .score{font-size:72px;font-weight:900;line-height:1}
        .pulse-big .unit{font-size:24px;font-weight:500;opacity:.8}
        .pulse-status{display:inline-block;padding:6px 20px;border-radius:6px;font-size:16px;font-weight:700;margin-top:8px}
        .pulse-status.expansion{background:#fff;color:var(--red)}
        .pulse-status.stable{background:#fff;color:var(--amber)}
        .pulse-status.contraction{background:#fff;color:var(--blue)}
        .pulse-status.warning{background:#fff;color:var(--gray)}
        .trend-badge{display:inline-block;margin-left:8px;font-size:14px;font-weight:600;padding:2px 10px;border-radius:4px;background:rgba(255,255,255,.2)}

        /* ===== CARDS ===== */
        .card{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:24px;margin-bottom:24px}
        .card-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
        .card-header h2{font-size:20px;font-weight:700;color:var(--dark)}
        .card-header .section-num{font-size:13px;color:var(--muted);font-weight:600}
        .card-body{position:relative}
        .card-body .chart-wrap{width:100%;overflow-x:auto}
        .card-body .chart-wrap .js-plotly-plot{margin:0 auto}

        /* ===== GAUGE STRIP (6 gauges in a row) ===== */
        .gauge-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}
        .mini-gauge{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:16px;text-align:center}
        .mini-gauge .gauge-label{font-size:13px;color:var(--muted);margin-bottom:8px;font-weight:600}
        .mini-gauge .gauge-value{font-size:32px;font-weight:800;margin:4px 0}
        .mini-gauge .gauge-change{font-size:12px}
        .mini-gauge .gauge-change.up{color:var(--red)}
        .mini-gauge .gauge-change.down{color:var(--blue)}

        /* ===== GRID LAYOUTS ===== */
        .grid-2{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:24px}
        .grid-3{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}
        .full-width{grid-column:1/-1}

        /* ===== DIVERGENCE TABLE ===== */
        .diverge-table{width:100%;border-collapse:collapse;font-size:14px}
        .diverge-table th{background:var(--red);color:#fff;padding:10px 14px;text-align:left;font-weight:600}
        .diverge-table td{padding:10px 14px;border-bottom:1px solid var(--border)}
        .diverge-table tr:nth-child(even) td{background:#FAFAFA}
        .severity-high{color:var(--red);font-weight:700}
        .severity-medium{color:var(--amber);font-weight:600}
        .direction-up{color:var(--red)}
        .direction-down{color:var(--blue)}

        /* ===== DATA TABLE ===== */
        .data-table-wrap{overflow-x:auto;max-height:500px;overflow-y:auto}
        .data-table{width:100%;border-collapse:collapse;font-size:12px;white-space:nowrap}
        .data-table thead{position:sticky;top:0;z-index:1}
        .data-table th{background:var(--red);color:#fff;padding:8px 10px;text-align:center;font-weight:600}
        .data-table td{padding:6px 10px;text-align:center;border-bottom:1px solid var(--border)}
        .data-table tr:nth-child(even) td{background:#FAFAFA}
        .data-table .pos{color:var(--red)}
        .data-table .neg{color:var(--blue)}

        /* ===== FOOTER ===== */
        .footer{background:var(--dark);color:#AAA;text-align:center;padding:32px 0;margin-top:48px;font-size:13px}
        .footer strong{color:#DDD}

        /* ===== ALERT BOX ===== */
        .alert{padding:14px 18px;border-radius:8px;margin-bottom:12px;font-size:14px;display:flex;align-items:flex-start;gap:10px}
        .alert-icon{font-size:20px;flex-shrink:0}
        .alert-warning{background:#FFF3CD;border-left:4px solid var(--amber);color:#856404}
        .alert-danger{background:#F8D7DA;border-left:4px solid var(--red);color:#721C24}
        .alert-info{background:#D1ECF1;border-left:4px solid var(--blue);color:#0C5460}

        /* ===== PRINT STYLES ===== */
        @media print{
            body{background:#fff;font-size:11px}
            .hero{background:var(--red)!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
            .card{box-shadow:none;border:1px solid #ddd;break-inside:avoid;page-break-inside:avoid}
            .gauge-strip{grid-template-columns:repeat(3,1fr)}
            .grid-2{grid-template-columns:1fr 1fr}
            .section{margin:16px 0}
        }

        /* ===== RESPONSIVE ===== */
        @media(max-width:768px){
            .hero h1{font-size:28px}
            .pulse-big .score{font-size:48px}
            .gauge-strip{grid-template-columns:repeat(2,1fr)}
            .grid-2{grid-template-columns:1fr}
            .grid-3{grid-template-columns:1fr}
            .container{padding:0 16px}
            .card{padding:16px}
        }
    </style>
</head>
<body>

<!-- ======== HERO / COVER ======== -->
<div class="hero">
    <div class="container">
        <div class="badge">CHINA ECONOMIC PULSE TRACKER</div>
        <h1>中国经济脉搏报告</h1>
        <div class="subtitle">月度宏观经济监测 -- 基于 {{total_indicators}} 项高频指标的综合分析</div>
        <div class="pulse-big">
            <span class="score">{{ pulse_score_str }}</span>
            <span class="unit">/ 100</span>
        </div>
        <br>
        <span class="pulse-status {{ pulse_level }}">{{ pulse_level_cn }}</span>
        <span class="trend-badge">{{ trend_arrow }} {{ trend_cn }}</span>
        <div class="meta">生成时间: {{ gen_time }} &middot; 数据来源: 国家统计局 / 中国人民银行 / 海关总署 / 财新 &middot; 数据接口: akshare</div>
    </div>
</div>

<div class="container">

<!-- ======== 1. PULSE GAUGE SECTION ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>经济脉搏指数</h2>
            <span class="section-num">SECTION 01</span>
        </div>
        <div class="card-body">
            <div class="grid-2">
                <div>{{ pulse_gauge_chart }}</div>
                <div>
                    <h3 style="margin-bottom:16px;color:var(--dark);font-size:16px">指数说明</h3>
                    <p style="color:var(--muted);font-size:14px;line-height:1.8;margin-bottom:16px">
                        <strong>经济脉搏指数</strong> 是一个加权综合指标，由以下8项领先指标合成：
                    </p>
                    <table style="width:100%;font-size:13px;border-collapse:collapse">
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">制造业PMI</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">20%</td>
                        </tr>
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">财新PMI</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">15%</td>
                        </tr>
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">用电量增速</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">15%</td>
                        </tr>
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">货运量增速</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">10%</td>
                        </tr>
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">新增贷款</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">10%</td>
                        </tr>
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">消费者信心</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">10%</td>
                        </tr>
                        <tr style="border-bottom:1px solid var(--border)">
                            <td style="padding:6px 0;color:var(--muted)">PPI同比</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">10%</td>
                        </tr>
                        <tr>
                            <td style="padding:6px 0;color:var(--muted)">社会零售</td>
                            <td style="padding:6px 0;text-align:right;font-weight:700">10%</td>
                        </tr>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ======== 2. CORE INDICATOR GAUGES ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>核心指标速览</h2>
            <span class="section-num">SECTION 02</span>
        </div>
        <div class="card-body">
            <div class="gauge-strip">
                {{ gauge_strip }}
            </div>
        </div>
    </div>
</div>

<!-- ======== 3. CALENDAR HEATMAP ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>经济热度日历</h2>
            <span class="section-num">SECTION 03</span>
        </div>
        <div class="card-body">
            {{ calendar_heatmap }}
        </div>
    </div>
</div>

<!-- ======== 4. RADAR + HEATMAP GRID ======== -->
<div class="section">
    <div class="grid-2">
        <div class="card">
            <div class="card-header">
                <h2>六维雷达图</h2>
                <span class="section-num">SECTION 04</span>
            </div>
            <div class="card-body">{{ radar_chart }}</div>
        </div>
        <div class="card">
            <div class="card-header">
                <h2>分类热度矩阵</h2>
                <span class="section-num">SECTION 04b</span>
            </div>
            <div class="card-body">{{ heatmap_grid_chart }}</div>
        </div>
    </div>
</div>

<!-- ======== 5. SMALL MULTIPLES ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>核心指标走势 (Small Multiples)</h2>
            <span class="section-num">SECTION 05</span>
        </div>
        <div class="card-body">{{ small_multiples_chart }}</div>
    </div>
</div>

<!-- ======== 6. LEADING INDICATORS ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>领先指标综合</h2>
            <span class="section-num">SECTION 06</span>
        </div>
        <div class="card-body">{{ leading_chart }}</div>
    </div>
</div>

<!-- ======== 7. PRICES ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>价格传导分析</h2>
            <span class="section-num">SECTION 07</span>
        </div>
        <div class="card-body">{{ price_chart }}</div>
    </div>
</div>

<!-- ======== 8. MONEY & FINANCE ======== -->
<div class="section">
    <div class="grid-2">
        <div class="card">
            <div class="card-header">
                <h2>M1-M2 剪刀差</h2>
                <span class="section-num">SECTION 08a</span>
            </div>
            <div class="card-body">{{ m1m2_chart }}</div>
        </div>
        <div class="card">
            <div class="card-header">
                <h2>社会融资规模</h2>
                <span class="section-num">SECTION 08b</span>
            </div>
            <div class="card-body">{{ social_financing_chart }}</div>
        </div>
    </div>
</div>

<!-- ======== 9. PROPERTY MARKET ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>房地产市场专项</h2>
            <span class="section-num">SECTION 09</span>
        </div>
        <div class="card-body">{{ property_chart }}</div>
    </div>
</div>

<!-- ======== 10. EARLY WARNING ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>预警信号</h2>
            <span class="section-num">SECTION 10</span>
        </div>
        <div class="card-body">
            {{ divergence_alerts }}
            {{ comparison_block }}
        </div>
    </div>
</div>

<!-- ======== 11. DATA APPENDIX ======== -->
<div class="section">
    <div class="card">
        <div class="card-header">
            <h2>数据附录</h2>
            <span class="section-num">SECTION 11</span>
        </div>
        <div class="card-body">
            <div class="data-table-wrap">
                {{ data_table }}
            </div>
        </div>
    </div>
</div>

</div><!-- .container -->

<!-- ======== FOOTER ======== -->
<div class="footer">
    <div class="container">
        <strong>China Econ Pulse</strong> &mdash; 中国经济脉搏监测系统 v1.0<br>
        数据来源: 国家统计局 | 中国人民银行 | 海关总署 | 国家能源局 | 交通运输部 | 财新/Markit<br>
        本报告由 <code>china-econ-pulse</code> 自动生成 &middot; {{ gen_time }}<br>
        免责声明: 本报告仅供研究参考，不构成任何投资建议。
    </div>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generate self-contained HTML economic pulse reports."""

    def __init__(self):
        self.viz = Visualizer()
        self.builder = PulseIndexBuilder()

    def generate_report(
        self,
        data_dict: Dict[str, pd.DataFrame],
        output_path: Path,
        include_title: bool = True,
    ) -> Path:
        """
        Generate the full HTML report.

        Parameters
        ----------
        data_dict : dict
            Dictionary of DataFrames from DataFetcher.fetch_all()
        output_path : Path
            Output HTML file path
        include_title : bool
            Whether to include the hero/cover section

        Returns
        -------
        Path to the generated HTML file
        """
        logger.info("Generating HTML report...")

        # ---- Merge all data into a single DataFrame ----
        merged_df = self._merge_data(data_dict)
        if merged_df.empty:
            logger.error("No data to generate report")
            return output_path

        # ---- Build pulse index ----
        pulse_df = self.builder.build_pulse_index(merged_df)
        latest_pulse = pulse_df.iloc[-1] if not pulse_df.empty else None

        # ---- Compute summaries ----
        summary = self.builder.summary(merged_df)
        radar_scores = summary["radar"]
        heatmap_df = self.builder.heat_map_scores(merged_df)
        divergences_df = self.builder.divergence_detect(merged_df)

        # ---- Build charts ----
        charts = self._build_all_charts(merged_df, pulse_df, heatmap_df, divergences_df, summary)

        # ---- Build gauge strip ----
        gauge_strip_html = self._build_gauge_strip(merged_df)

        # ---- Build data table ----
        data_table_html = self._build_data_table(merged_df)

        # ---- Build divergence alerts ----
        alert_html = self._build_divergence_alerts(divergences_df)

        # ---- Build comparison table ----
        comparison_html = self._build_comparison_block(merged_df)

        # ---- Render template ----
        level = summary.get("pulse_level", "stable")
        template = Template(REPORT_TEMPLATE)

        html = template.render(
            plotly_js=pio.to_html(
                charts["pulse_gauge"],
                include_plotlyjs=True,
                full_html=False,
            ).split('<div')[0] if charts["pulse_gauge"] else "",
            total_indicators=len(self.builder.config.get("indicators", [])),
            pulse_score_str=f"{summary.get('pulse_score', 0):.1f}" if summary.get("pulse_score") is not None else "N/A",
            pulse_level=level,
            pulse_level_cn=summary.get("pulse_level_cn", "N/A"),
            trend_arrow=PulseIndexBuilder.trend_arrow(summary.get("trend_signal", "")),
            trend_cn=summary.get("trend_signal_cn", "N/A"),
            gen_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
            pulse_gauge_chart=self._safe_chart_html(charts["pulse_gauge"]),
            gauge_strip=gauge_strip_html,
            calendar_heatmap=self._safe_chart_html(charts["calendar_heatmap"]),
            radar_chart=self._safe_chart_html(charts["radar"]),
            heatmap_grid_chart=self._safe_chart_html(charts["heatmap_grid"]),
            small_multiples_chart=self._safe_chart_html(charts["small_multiples"]),
            leading_chart=self._safe_chart_html(charts["leading"]),
            price_chart=self._safe_chart_html(charts["price"]),
            m1m2_chart=self._safe_chart_html(charts["m1m2"]),
            social_financing_chart=self._safe_chart_html(charts["social_financing"]),
            property_chart=self._safe_chart_html(charts["property"]),
            divergence_alerts=alert_html,
            comparison_block=comparison_html,
            data_table=data_table_html,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info("Report saved to %s", output_path)
        return output_path

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _safe_chart_html(self, chart: Optional[Any]) -> str:
        """Convert a Plotly figure to HTML string safely."""
        if chart is None:
            return '<p style="color:var(--muted);text-align:center;padding:40px">图表数据暂不可用</p>'
        try:
            return pio.to_html(chart, include_plotlyjs=False, full_html=False,
                               config={"displayModeBar": True, "responsive": True, "displaylogo": False})
        except Exception as e:
            logger.error("Chart conversion failed: %s", e)
            return '<p style="color:var(--muted);text-align:center;padding:40px">图表渲染失败</p>'

    def _merge_data(self, data_dict: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Merge all separate DataFrames into one by date."""
        frames = []
        for key, df in data_dict.items():
            if df is None or df.empty:
                continue
            df = df.copy()
            date_col = "date" if "date" in df.columns else "日期"
            if date_col not in df.columns:
                continue
            # Rename all date columns to 'date'
            if date_col != "date":
                df = df.rename(columns={date_col: "date"})
            df["date"] = pd.to_datetime(df["date"])
            # Rename columns to avoid conflicts: prepend key if needed
            # But our fetcher uses unique names already, so just merge
            frames.append(df)

        if not frames:
            return pd.DataFrame()

        merged = frames[0]
        for df in frames[1:]:
            # Find non-date columns that overlap
            overlap_cols = set(merged.columns) & set(df.columns) - {"date"}
            if overlap_cols:
                # Rename to avoid conflict
                rename_map = {c: f"{c}_dup" for c in overlap_cols}
                df = df.rename(columns=rename_map)
            merged = pd.merge(merged, df, on="date", how="outer")

        merged = merged.sort_values("date")
        return merged

    def _build_all_charts(
        self,
        merged_df: pd.DataFrame,
        pulse_df: pd.DataFrame,
        heatmap_df: pd.DataFrame,
        divergences_df: pd.DataFrame,
        summary: dict,
    ) -> Dict[str, Any]:
        """Build all charts for the report."""
        charts = {}
        df = merged_df.copy()
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns or df.empty:
            return charts

        # 1. Pulse gauge
        score = summary.get("pulse_score", 50.0) or 50.0
        level = summary.get("pulse_level", "stable") or "stable"
        signal = summary.get("trend_signal", "flat") or "flat"
        arrow = PulseIndexBuilder.trend_arrow(signal)
        charts["pulse_gauge"] = self.viz.pulse_gauge(score, level, signal, arrow)

        # 2. Calendar heatmap
        if not pulse_df.empty and "pulse_score" in pulse_df.columns:
            charts["calendar_heatmap"] = self.viz.heatmap_calendar(pulse_df, "pulse_score")
        else:
            charts["calendar_heatmap"] = None

        # 3. Radar chart
        radar_scores = summary.get("radar", {})
        if radar_scores:
            charts["radar"] = self.viz.indicator_radar(radar_scores)
        else:
            charts["radar"] = None

        # 4. Heatmap grid
        if not heatmap_df.empty:
            charts["heatmap_grid"] = self.viz.heatmap_grid(heatmap_df)
        else:
            charts["heatmap_grid"] = None

        # 5. Small multiples
        small_multiples = self._build_small_multiples_dict(df)
        if small_multiples:
            charts["small_multiples"] = self.viz.small_multiples(small_multiples, n_cols=3)
        else:
            charts["small_multiples"] = None

        # 6. Leading indicators
        leading_cols = [c for c in ["pmi_manufacturing", "caixin_pmi_manufacturing",
                                     "electricity", "freight_volume"] if c in df.columns]
        if leading_cols:
            leading_labels = ["制造业PMI", "财新PMI", "用电量增速", "货运量增速"]
            charts["leading"] = self.viz.multi_line_timeline(
                df, leading_cols, leading_labels, normalize=True
            )
        else:
            charts["leading"] = None

        # 7. Price (CPI vs PPI)
        if "cpi" in df.columns and "ppi" in df.columns:
            df_price = df.dropna(subset=["cpi", "ppi"])
            if len(df_price) > 2:
                charts["price"] = self.viz.dual_axis_timeline(
                    pd.to_numeric(df_price["cpi"], errors="coerce"),
                    pd.to_numeric(df_price["ppi"], errors="coerce"),
                    "CPI 同比 (%)", "PPI 同比 (%)",
                    df_price["date"],
                )
            else:
                charts["price"] = None
        else:
            charts["price"] = None

        # 8. M1-M2 scissors
        if all(c in df.columns for c in ["m1", "m2"]):
            charts["m1m2"] = self.viz.m1_m2_scissors_chart(df)
        else:
            charts["m1m2"] = None

        # 9. Social financing
        if any(c in df.columns for c in ["social_financing", "new_loans"]):
            charts["social_financing"] = self.viz.social_financing_chart(df)
        else:
            charts["social_financing"] = None

        # 10. Property dashboard
        prop_cols = ["new_home_prices", "floor_space_sold", "real_estate_investment"]
        if any(c in df.columns for c in prop_cols):
            charts["property"] = self.viz.property_dashboard(df)
        else:
            charts["property"] = None

        return charts

    def _build_small_multiples_dict(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Build dictionary of small DataFrames for small multiples."""
        indicators = [
            ("pmi_manufacturing", "制造业PMI"),
            ("caixin_pmi_manufacturing", "财新制造业PMI"),
            ("cpi", "CPI (同比%)"),
            ("ppi", "PPI (同比%)"),
            ("industrial_production", "工业增加值"),
            ("retail_sales", "社会零售"),
            ("fixed_asset_investment", "固定资产投资"),
            ("exports", "出口"),
            ("imports", "进口"),
            ("m2", "M2同比"),
            ("social_financing", "社融规模"),
            ("consumer_confidence", "消费者信心"),
        ]

        result = {}
        for col, label in indicators:
            if col in df.columns:
                sub = df[["date", col]].dropna(subset=[col]).copy()
                if len(sub) >= 3:
                    sub = sub.rename(columns={col: "value"})
                    result[label] = sub
        return result

    def _build_gauge_strip(self, df: pd.DataFrame) -> str:
        """Build mini gauge cards HTML."""
        gauge_items = [
            ("pmi_manufacturing", "制造业PMI", "%"),
            ("cpi", "CPI 同比", "%"),
            ("industrial_production", "工业增加值", "%"),
            ("retail_sales", "社会零售", "%"),
            ("exports", "出口金额", "亿美元"),
            ("m2", "M2 同比", "%"),
        ]

        html_parts = []
        for col, label, unit in gauge_items:
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals) < 2:
                continue
            latest = vals.iloc[-1]
            prev = vals.iloc[-2]
            change = latest - prev
            direction = "up" if change > 0 else "down" if change < 0 else ""
            sign = "+" if change > 0 else ""

            # Color the value
            if col in ["pmi_manufacturing"]:
                # PMI: 50 is neutral
                val_color = CHINA_RED if latest >= 50 else ACCENT_BLUE
            elif col in ["cpi", "ppi"]:
                val_color = TEXT_DARK
            else:
                val_color = CHINA_RED if change >= 0 else ACCENT_BLUE

            html_parts.append(f"""
            <div class="mini-gauge">
                <div class="gauge-label">{label}</div>
                <div class="gauge-value" style="color:{val_color}">{latest:.1f}</div>
                <div class="gauge-change {direction}">{sign}{change:.1f} {unit} MoM</div>
            </div>""")

        return "\n".join(html_parts) if html_parts else '<p style="color:var(--muted)">暂无核心指标数据</p>'

    def _build_data_table(self, df: pd.DataFrame) -> str:
        """Build HTML data table for appendix."""
        if df.empty:
            return '<p style="color:var(--muted)">暂无数据</p>'

        df = df.sort_values("date", ascending=False).head(36)
        if "date" not in df.columns:
            return '<p style="color:var(--muted)">暂无数据</p>'

        rows = []
        header_cols = ["日期"] + [c for c in df.columns if c != "date"]

        # Header
        rows.append("<thead><tr>")
        for col in header_cols:
            rows.append(f"<th>{col}</th>")
        rows.append("</tr></thead>")

        # Body
        rows.append("<tbody>")
        for _, row in df.iterrows():
            rows.append("<tr>")
            for col in header_cols:
                val = row.get(col)
                if col == "date":
                    dt = pd.Timestamp(val) if pd.notna(val) else None
                    date_str = dt.strftime("%Y-%m") if dt else "-"
                    rows.append(f"<td>{date_str}</td>")
                elif pd.isna(val):
                    rows.append("<td>-</td>")
                elif isinstance(val, (int, float)):
                    cls = "pos" if val > 0 else "neg" if val < 0 else ""
                    rows.append(f'<td class="{cls}">{val:.2f}</td>')
                else:
                    rows.append(f"<td>{val}</td>")
            rows.append("</tr>")
        rows.append("</tbody>")

        return f'<table class="data-table">{"".join(rows)}</table>'

    def _build_divergence_alerts(self, divergences_df: pd.DataFrame) -> str:
        """Build divergence alert HTML."""
        if divergences_df.empty:
            return '<div class="alert alert-info"><span class="alert-icon">&#9432;</span>当前未检测到显著指标背离信号。</div>'

        parts = []
        for _, row in divergences_df.iterrows():
            severity = row.get("severity", "medium")
            alert_class = "alert-warning" if severity == "high" else "alert-danger" if severity == "medium" else "alert-info"
            a_dir = row.get("a_direction", "")
            b_dir = row.get("b_direction", "")
            a_name = row.get("indicator_a", "")
            b_name = row.get("indicator_b", "")
            parts.append(f"""
            <div class="alert {alert_class}">
                <span class="alert-icon">{'&#9888;' if severity == 'high' else '&#9432;'}</span>
                <div>
                    <strong>{row.get('pair', '')} 背离</strong><br>
                    {a_name} <span class="direction-{'up' if '上升' in a_dir else 'down'}">{a_dir}</span>
                    &nbsp;vs&nbsp;
                    {b_name} <span class="direction-{'up' if '上升' in b_dir else 'down'}">{b_dir}</span>
                </div>
            </div>""")

        return "".join(parts)

    def _build_comparison_block(self, df: pd.DataFrame) -> str:
        """Build comparison table HTML."""
        key_cols = [
            ("pmi_manufacturing", "制造业PMI", "%"),
            ("pmi_non_manufacturing", "非制造业PMI", "%"),
            ("cpi", "CPI (同比)", "%"),
            ("ppi", "PPI (同比)", "%"),
            ("industrial_production", "工业增加值", "%"),
            ("retail_sales", "社会零售", "%"),
            ("fixed_asset_investment", "固定资产投资", "%"),
            ("exports", "出口金额", "亿美元"),
            ("imports", "进口金额", "亿美元"),
            ("trade_balance", "贸易差额", "亿美元"),
            ("m2", "M2 (同比)", "%"),
            ("m1", "M1 (同比)", "%"),
            ("social_financing", "社融规模", "亿元"),
            ("new_loans", "新增贷款", "亿元"),
            ("consumer_confidence", "消费者信心", "指数"),
        ]

        data_rows = []
        for col, name, unit in key_cols:
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce").dropna()
            if len(vals) < 2:
                continue
            latest = vals.iloc[-1]
            prev = vals.iloc[-2]
            change = latest - prev
            data_rows.append({
                "name": name, "latest": latest, "prev": prev,
                "change": change, "unit": unit,
            })

        if not data_rows:
            return ""

        chart = self.viz.comparison_table(data_rows)
        return self._safe_chart_html(chart)
