#!/usr/bin/env python3
# =============================================================================
# pulse.py -- China Econ Pulse CLI 入口
# =============================================================================
"""
中国经济脉搏监测系统 -- 命令行工具

用法:
    python pulse.py generate                生成完整报告
    python pulse.py generate --output report.html   指定输出路径
    python pulse.py pulse                   仅显示脉搏指数
    python pulse.py indicators              列出所有指标
    python pulse.py chart pmi              在浏览器中显示PMI图表
    python pulse.py compare pmi cpi         双轴对比图表
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

from china_econ_pulse.fetcher import DataFetcher
from china_econ_pulse.indicators import PulseIndexBuilder
from china_econ_pulse.viz import Visualizer
from china_econ_pulse.reporter import ReportGenerator

# -- Logging setup --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pulse")

# -- Output directory --
OUTPUT_DIR = _PROJECT_ROOT / "output"


def cmd_generate(args):
    """Generate full HTML report."""
    output = args.output or str(OUTPUT_DIR / f"china_econ_pulse_{datetime.now().strftime('%Y%m%d_%H%M')}.html")

    logger.info("China Econ Pulse - 开始生成报告...")

    # Fetch data
    fetcher = DataFetcher(use_cache=not args.no_cache)
    data = fetcher.fetch_all(force_refresh=args.refresh)

    # Merge into single dataframe
    reporter = ReportGenerator()
    merged = reporter._merge_data(data)

    if merged.empty:
        logger.error("无法获取任何数据，报告生成失败。请检查网络连接。")
        sys.exit(1)

    # Show pulse score
    builder = PulseIndexBuilder()
    pulse_df = builder.build_pulse_index(merged)
    if not pulse_df.empty:
        latest = pulse_df.iloc[-1]
        logger.info(
            "经济脉搏指数: %.1f / 100  [%s]  %s %s",
            latest["pulse_score"],
            builder.pulse_level_cn(latest["pulse_level"]),
            builder.trend_arrow(latest["trend_signal"]),
            builder.trend_signal_cn(latest["trend_signal"]),
        )

    # Generate report
    out_path = reporter.generate_report(data, Path(output))
    logger.info("报告已生成: %s", out_path)
    print(f"\n报告已保存: {out_path}")

    return 0


def cmd_pulse(args):
    """Show just the pulse index score."""
    fetcher = DataFetcher(use_cache=not args.no_cache)
    data = fetcher.fetch_all(force_refresh=args.refresh)

    reporter = ReportGenerator()
    merged = reporter._merge_data(data)

    if merged.empty:
        print("无法获取数据")
        return 1

    builder = PulseIndexBuilder()
    pulse_df = builder.build_pulse_index(merged)

    if pulse_df.empty:
        print("无法计算脉搏指数")
        return 1

    latest = pulse_df.iloc[-1]
    score = latest["pulse_score"]
    level = builder.pulse_level_cn(latest["pulse_level"])
    trend = builder.trend_signal_cn(latest["trend_signal"])
    arrow = builder.trend_arrow(latest["trend_signal"])

    print(f"\n  经济脉搏指数: {score:.1f} / 100")
    print(f"  状态: {level} {arrow} {trend}")
    print()

    # Show component breakdown if verbose
    if args.verbose:
        print("  子项得分:")
        comp_map_cn = {
            "pmi_manufacturing_score": "制造业PMI",
            "caixin_pmi_score": "财新PMI",
            "electricity_growth_score": "用电量增速",
            "freight_growth_score": "货运量增速",
            "new_loans_score": "新增贷款",
            "consumer_confidence_score": "消费者信心",
            "ppi_yoy_score": "PPI同比",
            "retail_sales_score": "社会零售",
        }
        for col, cn in comp_map_cn.items():
            if col in latest.index:
                v = latest[col]
                bar = "=" * max(1, int(v / 5))
                print(f"    {cn:12s} {v:5.1f}  {bar}")
        print()

    return 0


def cmd_indicators(args):
    """List all indicators from config."""
    builder = PulseIndexBuilder()
    indicators = builder.config.get("indicators", [])
    weights = builder.config.get("pulse_weights", {})

    print("\n  中国经济脉搏监测 -- 指标列表")
    print("  " + "=" * 60)
    print(f"  {'指标名称':<24s} {'来源':<12s} {'频率':<8s} {'权重':>6s}")
    print("  " + "-" * 60)

    for item in indicators:
        ind_id = item["id"]
        # Check if part of pulse index
        w = ""
        for k, v in weights.items():
            mapped = {
                "pmi_manufacturing": "pmi_manufacturing",
                "caixin_pmi": "caixin_pmi_manufacturing",
                "electricity_growth": "electricity",
                "freight_growth": "freight_volume",
                "new_loans": "new_loans",
                "consumer_confidence": "consumer_confidence",
                "ppi_yoy": "ppi",
                "retail_sales": "retail_sales",
            }
            if mapped.get(k) == ind_id:
                w = f"{v*100:.0f}%"
                break

        print(f"  {item['name']:<24s} {item['source']:<12s} {item['frequency']:<8s} {w:>6s}")

    print("  " + "=" * 60)
    print(f"  共 {len(indicators)} 项指标\n")
    return 0


def cmd_chart(args):
    """Show a single indicator chart in browser."""
    indicator = args.indicator.lower()
    fetcher = DataFetcher(use_cache=not args.no_cache)
    viz = Visualizer()

    # Map indicator names to fetch/filter methods
    indicator_map = {
        "pmi": lambda: fetcher.fetch_pmi(),
        "caixin": lambda: fetcher.fetch_caixin_pmi(),
        "cpi": lambda: fetcher.fetch_cpi_ppi(),
        "ppi": lambda: fetcher.fetch_cpi_ppi(),
        "industrial": lambda: fetcher.fetch_industrial_production(),
        "fai": lambda: fetcher.fetch_fixed_asset_investment(),
        "retail": lambda: fetcher.fetch_retail_sales(),
        "trade": lambda: fetcher.fetch_trade_data(),
        "money": lambda: fetcher.fetch_money_supply(),
        "social": lambda: fetcher.fetch_social_financing(),
        "electricity": lambda: fetcher.fetch_electricity(),
        "freight": lambda: fetcher.fetch_freight_volume(),
        "property": lambda: fetcher.fetch_property_market(),
        "confidence": lambda: fetcher.fetch_consumer_confidence(),
    }

    if indicator not in indicator_map:
        print(f"不支持的指标: {indicator}")
        print(f"可用指标: {', '.join(indicator_map.keys())}")
        return 1

    df = indicator_map[indicator]()
    if df.empty:
        print(f"指标 {indicator} 无可用数据")
        return 1

    # Create a simple line chart for the first numeric column
    date_col = "date" if "date" in df.columns else "日期"
    numeric_cols = [c for c in df.columns if c != date_col]
    if not numeric_cols:
        print("无可用数值列")
        return 1

    # Use multi-line timeline
    import plotly.graph_objects as go
    fig = viz.multi_line_timeline(df, numeric_cols[:4],
                                   labels=numeric_cols[:4], normalize=False)
    fig.show()

    print(f"已在浏览器中显示: {indicator}")
    return 0


def cmd_compare(args):
    """Compare two indicators on dual axis."""
    indicator1 = args.indicator1.lower()
    indicator2 = args.indicator2.lower()

    fetcher = DataFetcher(use_cache=not args.no_cache)
    viz = Visualizer()

    # Simple mapping: indicator -> (fetch_fn, col_name, label)
    def _get_series(ind_name):
        fetch_map = {
            "pmi": (fetcher.fetch_pmi, "pmi_manufacturing", "制造业PMI"),
            "cpi": (fetcher.fetch_cpi_ppi, "cpi", "CPI"),
            "ppi": (fetcher.fetch_cpi_ppi, "ppi", "PPI"),
            "m2": (fetcher.fetch_money_supply, "m2", "M2"),
            "m1": (fetcher.fetch_money_supply, "m1", "M1"),
            "retail": (fetcher.fetch_retail_sales, "retail_sales", "社会零售"),
            "industrial": (fetcher.fetch_industrial_production, "industrial_production", "工业增加值"),
            "exports": (fetcher.fetch_trade_data, "exports", "出口"),
            "imports": (fetcher.fetch_trade_data, "imports", "进口"),
            "electricity": (fetcher.fetch_electricity, "electricity", "用电量"),
            "freight": (fetcher.fetch_freight_volume, "freight_volume", "货运量"),
        }
        if ind_name not in fetch_map:
            return None, None, None
        fn, col, label = fetch_map[ind_name]
        df = fn()
        date_col = "date" if "date" in df.columns else "日期"
        if date_col not in df.columns or col not in df.columns:
            return None, None, None
        return df, col, label

    df1, col1, label1 = _get_series(indicator1)
    df2, col2, label2 = _get_series(indicator2)

    if df1 is None or df2 is None:
        print("无法获取指标数据，请检查指标名称")
        return 1

    # Merge on date
    date_col = "date" if "date" in df1.columns else "日期"
    df_m = df1.rename(columns={date_col: "date"})
    df2_m = df2.rename(columns={date_col: "date"} if date_col in df2.columns else {})

    merged = pd.merge(df_m[["date", col1]], df2_m[["date", col2]], on="date", how="inner")
    merged = merged.dropna(subset=[col1, col2]).sort_values("date")

    import pandas as pd
    fig = viz.dual_axis_timeline(
        pd.to_numeric(merged[col1], errors="coerce"),
        pd.to_numeric(merged[col2], errors="coerce"),
        label1, label2,
        merged["date"],
    )
    fig.show()

    print(f"已在浏览器中显示: {label1} vs {label2}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="China Econ Pulse - 中国经济脉搏监测系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pulse.py generate                    生成完整HTML报告
  python pulse.py generate --output my.html   指定输出文件
  python pulse.py pulse                       仅显示脉搏指数
  python pulse.py pulse -v                    显示子项得分
  python pulse.py indicators                  列出所有指标
  python pulse.py chart pmi                   在浏览器显示PMI图表
  python pulse.py compare pmi cpi             双轴对比PMI vs CPI
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- generate ----
    gen = subparsers.add_parser("generate", help="生成完整HTML报告")
    gen.add_argument("--output", "-o", help="输出文件路径")
    gen.add_argument("--refresh", action="store_true", help="强制刷新缓存")
    gen.add_argument("--no-cache", action="store_true", help="不使用缓存")
    gen.set_defaults(func=cmd_generate)

    # ---- pulse ----
    pul = subparsers.add_parser("pulse", help="显示脉搏指数")
    pul.add_argument("-v", "--verbose", action="store_true", help="显示子项得分")
    pul.add_argument("--refresh", action="store_true", help="强制刷新缓存")
    pul.add_argument("--no-cache", action="store_true", help="不使用缓存")
    pul.set_defaults(func=cmd_pulse)

    # ---- indicators ----
    ind = subparsers.add_parser("indicators", help="列出所有指标")
    ind.set_defaults(func=cmd_indicators)

    # ---- chart ----
    ch = subparsers.add_parser("chart", help="显示单个指标图表")
    ch.add_argument("indicator", help="指标名称 (pmi/cpi/ppi/retail/...等)")
    ch.add_argument("--no-cache", action="store_true", help="不使用缓存")
    ch.set_defaults(func=cmd_chart)

    # ---- compare ----
    cp = subparsers.add_parser("compare", help="双轴对比两个指标")
    cp.add_argument("indicator1", help="指标1")
    cp.add_argument("indicator2", help="指标2")
    cp.add_argument("--no-cache", action="store_true", help="不使用缓存")
    cp.set_defaults(func=cmd_compare)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
