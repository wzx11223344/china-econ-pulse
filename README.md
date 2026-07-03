# China Econ Pulse -- 中国经济脉搏监测系统

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Data: akshare](https://img.shields.io/badge/data-akshare-orange.svg)](https://github.com/akfamily/akshare)

**China Econ Pulse** 是一个专业的中国宏观经济监测系统。它从 akshare 抓取 30+ 高频经济指标，构建一个加权综合 **"经济脉搏指数" (Pulse Index)**，并生成美观的、自包含的 HTML 分析报告。

---

## 核心特性

- **脉搏指数 (Pulse Index)**: 由 8 项领先指标合成的 0-100 分综合打分，一目了然中国经济健康状况
- **四档状态判定**: 扩张 (>60) / 平稳 (40-60) / 收缩 (20-40) / 预警 (<20)
- **五级趋势信号**: 加速上行 / 温和回升 / 横盘整理 / 边际走弱 / 加速下行
- **六维雷达图**: 生产 / 需求 / 物价 / 金融 / 外贸 / 地产 六维度全景扫描
- **背离检测**: 自动识别指标间方向背离，提前预警结构性风险
- **自包含 HTML 报告**: 包含 11 个完整分析板块，所有 CSS/JS/图表内联，离线可用
- **30+ 项指标覆盖**: PMI、CPI、PPI、工业、零售、外贸、货币、社融、用电、货运、房地产、消费信心等
- **30 天 JSON 缓存**: 避免重复请求，提高响应速度
- **完全免费**: 基于 akshare 开源数据，无需任何 API Key

---

## 快速开始

### 安装

```bash
# 克隆项目
cd china-econ-pulse

# 安装依赖
pip install -r requirements.txt
```

### 生成报告

```bash
# 完整报告
python pulse.py generate

# 指定输出路径
python pulse.py generate --output my_report.html

# 强制刷新数据
python pulse.py generate --refresh
```

### 快速查看脉搏指数

```bash
python pulse.py pulse

# 显示子项得分
python pulse.py pulse -v
```

输出示例:
```
  经济脉搏指数: 52.3 / 100
  状态: 平稳 → 横盘整理

  子项得分:
    制造业PMI     55.2  ===========
    财新PMI       48.1  ==========
    用电量增速     53.0  ===========
    货运量增速     49.5  ==========
    新增贷款      50.8  ===========
    消费者信心     44.2  =========
    PPI同比       51.0  ===========
    社会零售      47.6  ==========
```

### 查看所有指标

```bash
python pulse.py indicators
```

### 单个图表

```bash
# 在浏览器中显示 PMI 走势
python pulse.py chart pmi

# 双轴对比 PMI vs CPI
python pulse.py compare pmi cpi
```

### 运行演示

```bash
python examples/demo.py
```

---

## 脉搏指数方法论

### 合成公式

脉搏指数是一个加权综合得分，由以下 8 项领先指标合成：

| 指标 | 权重 | 数据来源 | 说明 |
|------|------|----------|------|
| 制造业 PMI | 20% | 国家统计局 | 经济景气度最灵敏指标 |
| 财新 PMI | 15% | 财新/Markit | 中小企业/出口导向景气度 |
| 用电量增速 | 15% | 国家能源局 | "克强指数"成分，真实经济活动代理 |
| 货运量增速 | 10% | 交通运输部 | 物流活跃度，实体经济温度计 |
| 新增人民币贷款 | 10% | 中国人民银行 | 信用扩张速度 |
| 消费者信心 | 10% | 国家统计局 | 居民消费意愿 |
| PPI 同比 | 10% | 国家统计局 | 工业品价格与企业利润 |
| 社会零售增速 | 10% | 国家统计局 | 消费端需求强度 |

### 归一化方法

每项子指标采用 **Z-Score 映射法** 归一化到 0-100 分:

```
normalized_score = 50 + (z_score / 3) * 50
```

其中 z_score 基于该指标全部历史数据计算，[-3, 3] 范围映射到 [0, 100]，异常值截断处理。

### 趋势判定

| 月环比变化 | 趋势信号 |
|-----------|---------|
| >= +5.0 | 加速上行 |
| +1.0 ~ +5.0 | 温和回升 |
| -1.0 ~ +1.0 | 横盘整理 |
| -5.0 ~ -1.0 | 边际走弱 |
| < -5.0 | 加速下行 |

---

## 报告结构

生成的 HTML 报告包含以下 11 个板块:

| # | 板块 | 内容 |
|---|------|------|
| 01 | 经济脉搏指数 | Pulse Index 仪表盘 + 成分权重说明 |
| 02 | 核心指标速览 | 6 项关键指标迷你仪表板 |
| 03 | 经济热度日历 | 历史 Pulse Index 热力图 |
| 04 | 六维雷达图 | 生产/需求/物价/金融/外贸/地产 雷达图 + 热度矩阵 |
| 05 | 核心指标走势 | 12 项指标 Small Multiples 小图 |
| 06 | 领先指标综合 | PMI/用电/货运 归一化对比 |
| 07 | 价格传导分析 | CPI vs PPI 双轴走势 |
| 08 | 货币金融 | M1-M2 剪刀差 + 社融规模 |
| 09 | 房地产市场专项 | 房价/销售面积/投资 三联图 |
| 10 | 预警信号 | 背离检测 + 核心指标对比表 |
| 11 | 数据附录 | 36 个月完整数据表 |

---

## 项目结构

```
china-econ-pulse/
├── README.md
├── requirements.txt
├── pulse.py                  (CLI 入口)
├── china_econ_pulse/
│   ├── __init__.py
│   ├── fetcher.py            (akshare 数据抓取, 30天缓存)
│   ├── indicators.py         (脉搏指数构建, 背离检测)
│   ├── viz.py                (Plotly 可视化套件, 12种图表)
│   └── reporter.py           (自包含 HTML 报告生成)
├── config/
│   └── indicators.yaml       (指标定义, 权重, 阈值)
├── examples/
│   └── demo.py               (完整演示脚本)
└── output/
    └── .gitkeep
```

---

## 数据覆盖

| 类别 | 指标 | 频率 |
|------|------|------|
| PMI | 制造业PMI, 非制造业PMI, 财新制造业PMI, 财新服务业PMI | 月度 |
| 物价 | CPI, PPI | 月度 |
| 生产 | 工业增加值, 用电量, 货运量 | 月度 |
| 需求 | 社会零售, 固定资产投资, 消费者信心 | 月度 |
| 外贸 | 出口, 进口, 贸易差额 | 月度 |
| 货币 | M0, M1, M2, 社融规模, 新增贷款 | 月度 |
| 房地产 | 新建住宅价格, 销售面积, 开发投资 | 月度 |

---

## 依赖

```
akshare>=1.14.0
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
pyyaml>=6.0
jinja2>=3.0
```

---

## 许可

MIT License

---

## 免责声明

本系统仅供宏观经济研究参考，**不构成任何投资建议**。所有数据来源于公开统计渠道，作者不对数据的准确性、完整性承担任何责任。
