#!/usr/bin/env python3
# =============================================================================
# examples/demo.py -- 完整演示: 抓取数据 -> 构建指数 -> 生成报告
# =============================================================================
"""
中国经济脉搏监测系统完整演示。

运行:
    python examples/demo.py

将自动完成:
    1. 使用 akshare 抓取 30+ 宏观经济指标
    2. 构建经济脉搏指数 (Pulse Index)
    3. 显示指数得分与趋势信号
    4. 生成完整 HTML 报告
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from china_econ_pulse.fetcher import DataFetcher
from china_econ_pulse.indicators import PulseIndexBuilder
from china_econ_pulse.reporter import ReportGenerator

# -- Logging --
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo")

OUTPUT_DIR = _PROJECT_ROOT / "output"


def main():
    print("=" * 70)
    print("  China Econ Pulse -- 中国经济脉搏监测系统演示")
    print("=" * 70)
    print()

    # ========================
    # Step 1: Fetch data
    # ========================
    print("[Step 1] 正在抓取宏观经济数据 (通过 akshare)...")
    print("-" * 50)

    fetcher = DataFetcher(use_cache=True)
    data = fetcher.fetch_all()

    # Count successful fetches
    success_count = sum(1 for df in data.values() if not df.empty)
    total_rows = sum(len(df) for df in data.values() if not df.empty)
    print(f"\n  成功抓取: {success_count}/{len(data)} 类指标")
    print(f"  数据总量: {total_rows} 行")
    print()

    # ========================
    # Step 2: Build Pulse Index
    # ========================
    print("[Step 2] 正在构建经济脉搏指数...")
    print("-" * 50)

    reporter = ReportGenerator()
    merged = reporter._merge_data(data)

    if merged.empty:
        print("\n  错误: 无法合成数据，请检查网络连接后重试。")
        print("  提示: 首次运行需要下载 akshare 数据，请耐心等待。")
        return 1

    print(f"  合并后数据: {len(merged)} 行 × {len(merged.columns)} 列")
    print(f"  时间范围: {merged['date'].min().strftime('%Y-%m')} ~ {merged['date'].max().strftime('%Y-%m')}")

    builder = PulseIndexBuilder()
    pulse_df = builder.build_pulse_index(merged)

    if not pulse_df.empty:
        latest = pulse_df.iloc[-1]
        print()
        print("  " + "=" * 50)
        print(f"   经济脉搏指数 (Pulse Index)")
        print("  " + "=" * 50)
        print(f"   得分:    {latest['pulse_score']:.1f} / 100")
        print(f"   状态:    {builder.pulse_level_cn(latest['pulse_level'])}")
        print(f"   趋势:    {builder.trend_arrow(latest['trend_signal'])} {builder.trend_signal_cn(latest['trend_signal'])}")
        print(f"   月环比:  {latest['pulse_change']:+.1f}")
        print("  " + "=" * 50)
        print()

    # ========================
    # Step 3: Radar & Divergences
    # ========================
    print("[Step 3] 正在分析多维雷达图与背离信号...")
    print("-" * 50)

    radar = builder.radar_scores(merged)
    radar_cn = {"production": "生产", "demand": "需求", "prices": "物价",
                "finance": "金融", "trade": "外贸", "property": "地产"}
    for k, v in radar.items():
        bar = "=" * max(1, int(v / 5))
        print(f"  {radar_cn.get(k, k):6s} {v:5.1f} / 100  {bar}")

    divergences = builder.divergence_detect(merged)
    if not divergences.empty:
        print(f"\n  检测到 {len(divergences)} 个背离信号:")
        for _, row in divergences.iterrows():
            print(f"    - {row['pair']}: {row['indicator_a']} {row['a_direction']} vs {row['indicator_b']} {row['b_direction']}")
    else:
        print("\n  未检测到显著背离信号")
    print()

    # ========================
    # Step 4: Generate Report
    # ========================
    print("[Step 4] 正在生成 HTML 报告...")
    print("-" * 50)

    output_path = OUTPUT_DIR / f"china_econ_pulse_{datetime.now().strftime('%Y%m%d_%H%M')}.html"
    report_path = reporter.generate_report(data, output_path)

    print(f"\n  报告已生成!")
    print(f"  文件: {report_path}")
    print(f"  大小: {report_path.stat().st_size / 1024:.1f} KB")
    print()
    print("=" * 70)
    print(f"  请在浏览器中打开: file:///{report_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
