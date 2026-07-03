# =============================================================================
# china_econ_pulse/viz.py -- Plotly 可视化套件
# =============================================================================
"""
中国经济数据可视化套件。
所有图表使用统一配色（China Red #C41230 为主色），支持 PNG / HTML 导出。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from plotly.colors import qualitative, sequential
import plotly.io as pio

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color scheme
# ---------------------------------------------------------------------------

CHINA_RED = "#C41230"
CHINA_RED_LIGHT = "#E8553D"
CHINA_GOLD = "#D4A843"
DARK_BG = "#1A1A2E"
CARD_BG = "#FFFFFF"
TEXT_DARK = "#2D2D2D"
TEXT_MUTED = "#6B7280"
ACCENT_BLUE = "#4A90D9"
ACCENT_GREEN = "#27AE60"
ACCENT_AMBER = "#F5A623"
ACCENT_GRAY = "#7B7B7B"
GRID_COLOR = "#E5E7EB"

CATEGORY_COLORS = {
    "production": "#C41230",
    "demand": "#4A90D9",
    "prices": "#F5A623",
    "finance": "#27AE60",
    "trade": "#8E44AD",
    "property": "#7B7B7B",
}

PULSE_LEVEL_COLORS = {
    "expansion": "#C41230",
    "stable": "#F5A623",
    "contraction": "#4A90D9",
    "warning": "#7B7B7B",
}

# Default Plotly template
_DEFAULT_LAYOUT = dict(
    font=dict(family="Arial, 'Microsoft YaHei', sans-serif", size=12, color=TEXT_DARK),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(l=50, r=30, t=60, b=50),
    colorway=[CHINA_RED, ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_GRAY, CHINA_GOLD],
    xaxis=dict(showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
    hovermode="x unified",
)


def _apply_theme(fig: go.Figure) -> go.Figure:
    """Apply consistent styling to a figure."""
    fig.update_layout(**_DEFAULT_LAYOUT)
    return fig


# ===========================================================================
# Individual Charts
# ===========================================================================

class Visualizer:
    """Visualization suite for China economic pulse data."""

    def __init__(self):
        self.accent = CHINA_RED

    # -----------------------------------------------------------------------
    # 1. Pulse Gauge -- semi-circular gauge chart
    # -----------------------------------------------------------------------

    def pulse_gauge(
        self,
        pulse_score: float,
        pulse_level: str,
        trend_signal: str,
        trend_arrow: str,
    ) -> go.Figure:
        """
        Semi-circular gauge chart showing the Pulse Index with trend indicator.
        """
        level_cn_map = {"expansion": "扩张", "stable": "平稳", "contraction": "收缩", "warning": "预警"}
        trend_cn_map = {"strong_up": "加速上行", "mild_up": "温和回升", "flat": "横盘整理",
                        "mild_down": "边际走弱", "strong_down": "加速下行", "insufficient_data": "数据不足"}
        level_color = PULSE_LEVEL_COLORS.get(pulse_level, ACCENT_GRAY)

        # Build gauge using indicator trace
        fig = go.Figure()

        # Background arc
        fig.add_trace(go.Indicator(
            mode="gauge+number+delta",
            value=pulse_score,
            number={
                "font": {"size": 56, "color": level_color, "family": "Arial"},
                "suffix": " 分",
            },
            delta={"reference": 50, "increasing": {"color": CHINA_RED}, "decreasing": {"color": ACCENT_BLUE}},
            title={
                "text": f"<b>经济脉搏指数</b><br><span style='font-size:14px;color:{TEXT_MUTED}'>"
                        f"{level_cn_map.get(pulse_level, pulse_level)} · {trend_arrow} {trend_cn_map.get(trend_signal, trend_signal)}</span>",
                "font": {"size": 18, "color": TEXT_DARK},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": TEXT_DARK,
                    "tickmode": "array",
                    "tickvals": [0, 20, 40, 60, 80, 100],
                    "ticktext": ["0", "20<br>预警", "40<br>收缩", "60<br>平稳", "80<br>扩张", "100"],
                },
                "bar": {"color": level_color, "thickness": 0.25},
                "bgcolor": "white",
                "borderwidth": 0,
                "threshold": {
                    "line": {"color": TEXT_DARK, "width": 2},
                    "thickness": 0.8,
                    "value": 50,
                },
                "steps": [
                    {"range": [0, 20], "color": "#E8E8E8"},
                    {"range": [20, 40], "color": "#D6E4F0"},
                    {"range": [40, 60], "color": "#FDEBD0"},
                    {"range": [60, 100], "color": "#F5B7B1"},
                ],
            },
            domain={"row": 0, "column": 0},
        ))

        fig.update_layout(
            height=300,
            margin=dict(l=30, r=30, t=80, b=10),
            paper_bgcolor="white",
            font=dict(family="Arial, 'Microsoft YaHei', sans-serif"),
        )
        return fig

    # -----------------------------------------------------------------------
    # 2. Indicator Radar Chart
    # -----------------------------------------------------------------------

    def indicator_radar(self, category_scores: Dict[str, float]) -> go.Figure:
        """
        6-dimension radar chart: production, demand, prices, finance, trade, property.
        """
        cn_map = {"production": "生产", "demand": "需求", "prices": "物价",
                  "finance": "金融", "trade": "外贸", "property": "地产"}
        categories = list(cn_map.keys())
        values = [category_scores.get(c, 50.0) for c in categories]
        labels = [cn_map[c] for c in categories]

        # Close the loop
        values_closed = values + [values[0]]
        labels_closed = labels + [labels[0]]

        colors = [CATEGORY_COLORS.get(c, ACCENT_GRAY) for c in categories]
        fill_colors = [c.replace(")", ", 0.25)").replace("rgb(", "rgba(") if c.startswith("rgb(") else
                       f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.25)"
                       for c in colors]

        fig = go.Figure()

        fig.add_trace(go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor="rgba(196, 18, 48, 0.15)",
            line=dict(color=CHINA_RED, width=2.5),
            name="当前值",
            hovertemplate="%{theta}: <b>%{r:.1f}</b><extra></extra>",
        ))

        # Reference line at 50
        fig.add_trace(go.Scatterpolar(
            r=[50] * len(labels) + [50],
            theta=labels_closed,
            fill="none",
            line=dict(color=GRID_COLOR, width=1, dash="dash"),
            name="基准线 (50)",
            hoverinfo="skip",
        ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    showticklabels=True,
                    tickfont=dict(size=10),
                    gridcolor=GRID_COLOR,
                ),
                angularaxis=dict(
                    tickfont=dict(size=13, color=TEXT_DARK),
                    gridcolor=GRID_COLOR,
                ),
                bgcolor="white",
            ),
            height=450,
            margin=dict(l=50, r=50, t=50, b=50),
            showlegend=False,
            paper_bgcolor="white",
        )
        return fig

    # -----------------------------------------------------------------------
    # 3. Calendar Heatmap
    # -----------------------------------------------------------------------

    def heatmap_calendar(self, monthly_data: pd.DataFrame, column: str = "pulse_score") -> go.Figure:
        """
        Calendar-style heatmap for monthly data (like GitHub contribution grid).
        """
        df = monthly_data.copy()
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns or column not in df.columns:
            return go.Figure()

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).dropna(subset=[column])

        df["year"] = df[date_col].dt.year
        df["month"] = df[date_col].dt.month
        df["month_name"] = df[date_col].dt.strftime("%b")
        df["year_month"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)

        # Create a matrix: rows=years, cols=months
        pivot = df.pivot_table(index="year", columns="month", values=column, aggfunc="last")
        # Ensure all months 1-12
        for m in range(1, 13):
            if m not in pivot.columns:
                pivot[m] = np.nan
        pivot = pivot.sort_index(axis=1)

        years = pivot.index.tolist()
        months = list(range(1, 13))
        month_labels = ["1月", "2月", "3月", "4月", "5月", "6月",
                        "7月", "8月", "9月", "10月", "11月", "12月"]

        z_data = pivot.values
        text_data = [[f"{v:.1f}" if not np.isnan(v) else "" for v in row] for row in z_data]

        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=month_labels,
            y=[str(y) for y in years],
            text=text_data,
            texttemplate="%{text}",
            textfont={"size": 10, "family": "Arial"},
            colorscale=[
                [0.0, ACCENT_GRAY],
                [0.25, ACCENT_BLUE],
                [0.5, ACCENT_AMBER],
                [0.75, CHINA_RED_LIGHT],
                [1.0, CHINA_RED],
            ],
            zmin=0,
            zmax=100,
            xgap=4,
            ygap=4,
            hovertemplate="%{y}年 %{x}<br>分值: <b>%{z:.1f}</b><extra></extra>",
        ))

        fig.update_layout(
            height=max(180, len(years) * 40 + 80),
            margin=dict(l=10, r=20, t=30, b=10),
            xaxis=dict(title=None, side="top", tickfont=dict(size=11)),
            yaxis=dict(title=None, autorange="reversed", tickfont=dict(size=12)),
            paper_bgcolor="white",
            plot_bgcolor="white",
            coloraxis_showscale=False,
        )
        return fig

    # -----------------------------------------------------------------------
    # 4. Dual-Axis Timeline
    # -----------------------------------------------------------------------

    def dual_axis_timeline(
        self,
        series1: pd.Series,
        series2: pd.Series,
        label1: str = "Series 1",
        label2: str = "Series 2",
        dates: Optional[pd.Series] = None,
        threshold_line: Optional[float] = None,
    ) -> go.Figure:
        """
        Dual y-axis time series chart (e.g., PMI vs CPI).
        """
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        x = dates if dates is not None else list(range(len(series1)))

        fig.add_trace(
            go.Scatter(
                x=x, y=series1.values,
                name=label1,
                line=dict(color=CHINA_RED, width=2.5),
                mode="lines+markers",
                marker=dict(size=4),
                hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}</b><extra></extra>",
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=x, y=series2.values,
                name=label2,
                line=dict(color=ACCENT_BLUE, width=2.5),
                mode="lines+markers",
                marker=dict(size=4),
                hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}</b><extra></extra>",
            ),
            secondary_y=True,
        )

        if threshold_line is not None:
            fig.add_hline(y=threshold_line, line_dash="dash", line_color=ACCENT_GRAY,
                          opacity=0.5, annotation_text=f"{threshold_line}")

        fig.update_xaxes(title_text="")
        fig.update_yaxes(title_text=label1, secondary_y=False, title_font_color=CHINA_RED)
        fig.update_yaxes(title_text=label2, secondary_y=True, title_font_color=ACCENT_BLUE)

        fig.update_layout(
            height=380,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=50, r=50, t=50, b=40),
        )
        return _apply_theme(fig)

    # -----------------------------------------------------------------------
    # 5. Small Multiples
    # -----------------------------------------------------------------------

    def small_multiples(
        self,
        indicator_dict: Dict[str, pd.DataFrame],
        n_cols: int = 3,
    ) -> go.Figure:
        """
        Small multiple line charts for 12+ indicators.
        indicator_dict: {label: DataFrame with columns [date, value]}
        """
        items = list(indicator_dict.items())
        if not items:
            return go.Figure()

        n_rows = (len(items) + n_cols - 1) // n_cols
        fig = make_subplots(
            rows=n_rows, cols=n_cols,
            subplot_titles=[label for label, _ in items],
            vertical_spacing=0.08,
            horizontal_spacing=0.06,
        )

        for idx, (label, df) in enumerate(items):
            row = idx // n_cols + 1
            col = idx % n_cols + 1

            date_col = "date" if "date" in df.columns else df.columns[0]
            val_col = "value" if "value" in df.columns else df.columns[-1]

            dates = pd.to_datetime(df[date_col]) if date_col in df.columns else df.index
            vals = pd.to_numeric(df[val_col], errors="coerce") if val_col in df.columns else df.iloc[:, 0]

            fig.add_trace(
                go.Scatter(
                    x=dates, y=vals,
                    mode="lines",
                    line=dict(color=CHINA_RED, width=1.5),
                    name=label,
                    showlegend=False,
                    hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}</b><extra></extra>",
                ),
                row=row, col=col,
            )

            # Add a zero/horizontal reference line
            fig.add_hline(y=0, line_dash="dot", line_color=GRID_COLOR, opacity=0.5,
                          row=row, col=col)

            fig.update_xaxes(showticklabels=True, tickfont=dict(size=9), row=row, col=col)
            fig.update_yaxes(showticklabels=True, tickfont=dict(size=9), row=row, col=col)

        fig.update_layout(
            height=280 * n_rows,
            margin=dict(l=40, r=40, t=60, b=30),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        return fig

    # -----------------------------------------------------------------------
    # 6. Nowcast Ribbon Chart
    # -----------------------------------------------------------------------

    def nowcast_ribbon(
        self,
        dates: pd.Series,
        central: pd.Series,
        lower_band: pd.Series,
        upper_band: pd.Series,
        label: str = "GDP Nowcast",
    ) -> go.Figure:
        """Nowcast ribbon chart with confidence bands."""
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=list(dates) + list(dates[::-1]),
            y=list(upper_band.values) + list(lower_band.values[::-1]),
            fill="toself",
            fillcolor="rgba(196, 18, 48, 0.12)",
            line=dict(color="rgba(255,255,255,0)"),
            name="置信区间",
            hoverinfo="skip",
        ))

        fig.add_trace(go.Scatter(
            x=dates, y=central.values,
            mode="lines+markers",
            line=dict(color=CHINA_RED, width=3),
            marker=dict(size=5, color=CHINA_RED),
            name=label,
            hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}%</b><extra></extra>",
        ))

        fig.add_hline(y=0, line_dash="dash", line_color=ACCENT_GRAY, opacity=0.5)

        fig.update_layout(
            height=350,
            xaxis_title="",
            yaxis_title="同比增速 (%)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(l=50, r=30, t=50, b=40),
        )
        return _apply_theme(fig)

    # -----------------------------------------------------------------------
    # 7. Waterfall Chart
    # -----------------------------------------------------------------------

    def waterfall_chart(self, components: Dict[str, float], title: str = "GDP增速分解") -> go.Figure:
        """
        Waterfall chart showing component contributions.
        components: {label: contribution_value}
        """
        labels = list(components.keys())
        values = list(components.values())

        # Build waterfall
        fig = go.Figure(go.Waterfall(
            name="",
            orientation="v",
            measure=["relative"] * len(labels),
            x=labels,
            y=values,
            text=[f"{v:+.2f}%" for v in values],
            textposition="outside",
            connector={"line": {"color": GRID_COLOR}},
            decreasing={"marker": {"color": ACCENT_BLUE}},
            increasing={"marker": {"color": CHINA_RED}},
            totals={"marker": {"color": ACCENT_AMBER}},
        ))

        fig.update_layout(
            title=dict(text=title, font=dict(size=16, color=TEXT_DARK)),
            height=380,
            margin=dict(l=40, r=40, t=60, b=50),
            showlegend=False,
            yaxis=dict(title="贡献 (% ppt)"),
        )
        return _apply_theme(fig)

    # -----------------------------------------------------------------------
    # 8. M1-M2 Scissors Chart
    # -----------------------------------------------------------------------

    def m1_m2_scissors_chart(self, df: pd.DataFrame) -> go.Figure:
        """
        M1-M2 scissors gap visualization.
        df must have columns: date, m1, m2
        """
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns:
            return go.Figure()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)

        m1 = pd.to_numeric(df.get("m1", pd.Series()), errors="coerce")
        m2 = pd.to_numeric(df.get("m2", pd.Series()), errors="coerce")
        scissors = m1 - m2

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.65, 0.35],
        )

        # Top: M1 and M2 lines
        fig.add_trace(
            go.Scatter(x=df[date_col], y=m1, name="M1 同比",
                       line=dict(color=CHINA_RED, width=2),
                       hovertemplate="%{x|%Y-%m}: <b>%{y:.1f}%</b><extra></extra>"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=df[date_col], y=m2, name="M2 同比",
                       line=dict(color=ACCENT_BLUE, width=2),
                       hovertemplate="%{x|%Y-%m}: <b>%{y:.1f}%</b><extra></extra>"),
            row=1, col=1,
        )

        # Bottom: Scissors gap as bar
        colors = [CHINA_RED if v >= 0 else ACCENT_BLUE for v in scissors]
        fig.add_trace(
            go.Bar(x=df[date_col], y=scissors, name="M1-M2 剪刀差",
                   marker_color=colors, opacity=0.8,
                   hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}</b><extra></extra>"),
            row=2, col=1,
        )
        fig.add_hline(y=0, line_dash="dash", line_color=ACCENT_GRAY, opacity=0.5, row=2, col=1)

        fig.update_yaxes(title_text="同比 (%)", row=1, col=1)
        fig.update_yaxes(title_text="剪刀差 (ppt)", row=2, col=1)
        fig.update_layout(
            height=450,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=50, r=30, t=50, b=30),
            showlegend=True,
        )
        return _apply_theme(fig)

    # -----------------------------------------------------------------------
    # 9. Social Financing Bar Chart
    # -----------------------------------------------------------------------

    def social_financing_chart(self, df: pd.DataFrame) -> go.Figure:
        """Bar chart for social financing and new loans."""
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns:
            return go.Figure()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).tail(24)  # Last 24 months

        fig = go.Figure()

        if "social_financing" in df.columns:
            fig.add_trace(go.Bar(
                x=df[date_col], y=df["social_financing"],
                name="社会融资规模",
                marker_color=CHINA_RED,
                opacity=0.85,
                hovertemplate="%{x|%Y-%m}: <b>%{y:.0f}</b> 亿元<extra></extra>",
            ))

        if "new_loans" in df.columns:
            fig.add_trace(go.Scatter(
                x=df[date_col], y=df["new_loans"],
                name="新增人民币贷款",
                line=dict(color=ACCENT_BLUE, width=2.5),
                mode="lines+markers",
                marker=dict(size=5),
                hovertemplate="%{x|%Y-%m}: <b>%{y:.0f}</b> 亿元<extra></extra>",
            ))

        fig.update_layout(
            height=380,
            yaxis_title="亿元",
            barmode="overlay",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            margin=dict(l=50, r=30, t=50, b=40),
        )
        return _apply_theme(fig)

    # -----------------------------------------------------------------------
    # 10. Property Market 3-Chart Grid
    # -----------------------------------------------------------------------

    def property_dashboard(self, df: pd.DataFrame) -> go.Figure:
        """
        3-chart grid: prices, floor space sold, real estate investment.
        """
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns:
            return go.Figure()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).tail(36)

        charts = [
            ("new_home_prices", "新建住宅价格 (环比%)", CHINA_RED),
            ("floor_space_sold", "商品房销售面积 (同比%)", ACCENT_BLUE),
            ("real_estate_investment", "房地产开发投资 (同比%)", ACCENT_GREEN),
        ]

        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=[title for _, title, _ in charts],
            horizontal_spacing=0.08,
        )

        for idx, (col, title, color) in enumerate(charts):
            if col in df.columns:
                vals = pd.to_numeric(df[col], errors="coerce")
                fig.add_trace(
                    go.Scatter(
                        x=df[date_col], y=vals,
                        mode="lines",
                        line=dict(color=color, width=2),
                        name=title,
                        showlegend=False,
                        hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}</b><extra></extra>",
                    ),
                    row=1, col=idx + 1,
                )
            fig.add_hline(y=0, line_dash="dot", line_color=GRID_COLOR, opacity=0.5,
                          row=1, col=idx + 1)

        fig.update_layout(
            height=320,
            margin=dict(l=30, r=30, t=80, b=30),
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        return fig

    # -----------------------------------------------------------------------
    # 11. Comparison Table (as Plotly table)
    # -----------------------------------------------------------------------

    def comparison_table(
        self,
        indicators_data: List[Dict[str, Any]],
    ) -> go.Figure:
        """
        Styled comparison table with latest, previous, and YoY change.
        indicators_data: list of dicts with keys: name, latest, prev, change, unit
        """
        headers = ["指标", "最新值", "前值", "变动", "单位"]
        cells = [[], [], [], [], []]

        for item in indicators_data:
            cells[0].append(item.get("name", ""))
            cells[1].append(f"{item.get('latest', '-'):.2f}" if isinstance(item.get("latest"), (int, float)) else str(item.get("latest", "-")))
            cells[2].append(f"{item.get('prev', '-'):.2f}" if isinstance(item.get("prev"), (int, float)) else str(item.get("prev", "-")))
            change = item.get("change")
            if isinstance(change, (int, float)):
                sign = "+" if change > 0 else ""
                color_tag = f'<span style="color:{CHINA_RED}">' if change > 0 else f'<span style="color:{ACCENT_BLUE}">'
                cells[3].append(f'{color_tag}{sign}{change:.2f}</span>')
            else:
                cells[3].append(str(change or "-"))
            cells[4].append(item.get("unit", ""))

        fig = go.Figure(data=[go.Table(
            header=dict(
                values=headers,
                fill_color=CHINA_RED,
                font=dict(color="white", size=12, family="Arial, 'Microsoft YaHei'"),
                align="center",
                height=32,
            ),
            cells=dict(
                values=cells,
                fill_color=[["#FAFAFA", "white"] * (len(cells[0]) // 2 + 1)],
                font=dict(size=11, color=TEXT_DARK, family="Arial, 'Microsoft YaHei'"),
                align=["left", "center", "center", "center", "center"],
                height=28,
            ),
        )])

        fig.update_layout(
            height=32 * len(cells[0]) + 70,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        return fig

    # -----------------------------------------------------------------------
    # 12. Heatmap Grid (categories x months)
    # -----------------------------------------------------------------------

    def heatmap_grid(self, heatmap_df: pd.DataFrame) -> go.Figure:
        """
        5xN heatmap: categories vs months, color-coded.
        """
        if heatmap_df.empty:
            return go.Figure()

        pivot = heatmap_df.pivot_table(
            index="category_cn", columns="date", values="score", aggfunc="last"
        )
        pivot = pivot.sort_index()

        dates_str = [d.strftime("%Y-%m") if hasattr(d, "strftime") else str(d) for d in pivot.columns]
        categories = pivot.index.tolist()

        fig = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=dates_str,
            y=categories,
            colorscale=[
                [0.0, ACCENT_BLUE],
                [0.35, "#A8D0E6"],
                [0.5, "#F8E9A1"],
                [0.65, "#F5B7B1"],
                [1.0, CHINA_RED],
            ],
            zmin=0,
            zmax=100,
            xgap=3,
            ygap=3,
            text=[[f"{v:.1f}" if not np.isnan(v) else "" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="%{y} · %{x}<br>评分: <b>%{z:.1f}</b><extra></extra>",
        ))

        fig.update_layout(
            height=280,
            margin=dict(l=10, r=20, t=30, b=10),
            xaxis=dict(title=None, side="top", tickfont=dict(size=10)),
            yaxis=dict(title=None, tickfont=dict(size=12)),
            paper_bgcolor="white",
            plot_bgcolor="white",
            coloraxis_showscale=False,
        )
        return fig

    # -----------------------------------------------------------------------
    # 13. Timeline with multiple indicators (for leading indicators section)
    # -----------------------------------------------------------------------

    def multi_line_timeline(
        self,
        df: pd.DataFrame,
        columns: List[str],
        labels: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        normalize: bool = True,
    ) -> go.Figure:
        """
        Multi-line chart with optional normalization.
        """
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns:
            return go.Figure()

        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)

        if labels is None:
            labels = columns
        if colors is None:
            default_colors = [CHINA_RED, ACCENT_BLUE, ACCENT_GREEN, ACCENT_AMBER, ACCENT_GRAY, CHINA_GOLD]
            colors = default_colors[:len(columns)]

        fig = go.Figure()

        for idx, col in enumerate(columns):
            if col not in df.columns:
                continue
            vals = pd.to_numeric(df[col], errors="coerce")
            if normalize:
                mu, sigma = vals.mean(), vals.std(ddof=1)
                if sigma and not pd.isna(sigma):
                    vals = (vals - mu) / sigma

            color = colors[idx % len(colors)]
            label = labels[idx] if idx < len(labels) else col
            fig.add_trace(go.Scatter(
                x=df[date_col], y=vals,
                mode="lines",
                line=dict(color=color, width=2),
                name=label,
                hovertemplate="%{x|%Y-%m}: <b>%{y:.2f}</b><extra></extra>",
            ))

        fig.update_layout(
            height=380,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            yaxis_title="标准化值" if normalize else "",
            margin=dict(l=50, r=30, t=50, b=40),
        )
        return _apply_theme(fig)

    # -----------------------------------------------------------------------
    # Export helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def to_html(fig: go.Figure, include_plotlyjs: bool = True) -> str:
        """Convert figure to standalone HTML string."""
        return pio.to_html(
            fig,
            include_plotlyjs=include_plotlyjs,
            full_html=False,
            config={
                "displayModeBar": True,
                "responsive": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
            },
        )

    @staticmethod
    def to_image(fig: go.Figure, path: str, width: int = 1200, height: int = 600):
        """Save figure as PNG. Requires kaleido package."""
        try:
            fig.write_image(path, width=width, height=height, scale=2)
            logger.info("Saved chart to %s", path)
        except Exception as e:
            logger.warning("Could not save image (kaleido needed): %s", e)

    @staticmethod
    def show(fig: go.Figure):
        """Open figure in default browser."""
        fig.show()
