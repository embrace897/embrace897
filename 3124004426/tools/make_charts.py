"""生成博客里使用的图表（需要 matplotlib，仅文档用途）。

图表数据全部来自 ``docs/evidence/`` 下的原始输出文件，不手工填写数字：

* fig1-flow.png       算法与模块流程图
* fig2-performance.png 性能改进前后对比（墙钟耗时 / 函数调用次数）
* fig3-hotspots.png    热点函数耗时对比（cProfile tottime）
* fig4-coverage.png    各模块单元测试覆盖率

用法（在项目根目录下）::

    python tools/make_charts.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, NamedTuple, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
EVIDENCE_DIR = DOCS_DIR / "evidence"
IMAGE_DIR = DOCS_DIR / "images"

#: matplotlib 需要在可写目录下建立缓存（沙箱/CI 环境下默认目录可能不可写）。
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT.parent.parent.parent / "work" / "mpl"))

import matplotlib  # pylint: disable=wrong-import-position

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # pylint: disable=wrong-import-position
from matplotlib import font_manager, patches  # pylint: disable=wrong-import-position

#: 中文字体候选（Windows 自带字体，缺失时退回 matplotlib 默认字体）。
_FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\simhei.ttf"),
    Path(r"C:\Windows\Fonts\msyh.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
)

_COLOR_BEFORE = "#b0b0b0"
_COLOR_AFTER = "#2f6fb5"
_COLOR_ACCENT = "#d05a3c"


class BarPanel(NamedTuple):
    """一组对比柱状图的绘制参数。"""

    title: str
    unit: str
    color: str
    number_format: str


def setup_font() -> None:
    """选择一个支持中文的字体。"""
    for path in _FONT_CANDIDATES:
        if path.exists():
            font_manager.fontManager.addfont(str(path))
            name = font_manager.FontProperties(fname=str(path)).get_name()
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def read_text(path: Path) -> str:
    """读取证据文件。"""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_wall_time(text: str) -> float:
    """从性能报告里取出平均耗时（秒）。"""
    match = re.search(r"平均耗时 ([\d.]+) s", text)
    if not match:
        raise ValueError("未找到平均耗时")
    return float(match.group(1))


def parse_call_count(text: str) -> int:
    """从 cProfile 输出里取出函数调用次数。"""
    match = re.search(r"(\d+) function calls", text)
    if not match:
        raise ValueError("未找到函数调用次数")
    return int(match.group(1))


def parse_hotspots(text: str, limit: int = 6) -> List[Tuple[str, float]]:
    """解析 cProfile 表格，取出耗时最高的若干函数。"""
    rows: List[Tuple[str, float]] = []
    pattern = re.compile(
        r"^\s*\d+\s+([\d.]+)\s+[\d.]+\s+([\d.]+)\s+[\d.]+\s+(\S.*?)\s*$", re.MULTILINE
    )
    for match in pattern.finditer(text):
        tottime = float(match.group(1))
        target = match.group(3)
        rows.append((_short_name(target), tottime))
    return rows[:limit]


def _short_name(target: str) -> str:
    """把 ``...tokenizer.py:51(_extract_run_tokens)`` 压缩成函数名。"""
    if target.startswith("{"):
        return target.strip("{}").split()[-1]
    match = re.search(r"\(([^)]*)\)$", target)
    return match.group(1) if match else target


def parse_coverage(text: str) -> List[Tuple[str, float]]:
    """解析 coverage report 输出。"""
    rows = []
    for line in text.splitlines():
        match = re.match(r"^(papercheck\\|papercheck/)(\S+)\s+.*?(\d+)%\s*$", line.strip())
        if match:
            rows.append((match.group(2), float(match.group(3))))
    total = re.search(r"^TOTAL.*?(\d+)%\s*$", text, re.MULTILINE)
    if total:
        rows.append(("总体", float(total.group(1))))
    return rows


def _draw_flow_boxes(axis, boxes: List[Tuple[float, float, float, float, str, str]]) -> None:
    """在坐标轴上画出流程图的圆角矩形与文字。"""
    for x_pos, y_pos, width, height, label, color in boxes:
        axis.add_patch(
            patches.FancyBboxPatch(
                (x_pos, y_pos),
                width,
                height,
                boxstyle="round,pad=0.06",
                linewidth=1.2,
                edgecolor="#5a6b7d",
                facecolor=color,
            )
        )
        axis.text(
            x_pos + width / 2,
            y_pos + height / 2,
            label,
            ha="center",
            va="center",
            fontsize=10,
        )


def _draw_arrow(axis, start: Tuple[float, float], end: Tuple[float, float]) -> None:
    """画一条带箭头的连线。"""
    axis.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={"arrowstyle": "->", "color": "#5a6b7d", "linewidth": 1.2},
    )


def figure_flow() -> Path:
    """绘制算法与模块流程图（精简后的 4 个文件）。"""
    fig, axis = plt.subplots(figsize=(9.6, 5.2))
    axis.set_xlim(0, 10)
    axis.set_ylim(0, 6)
    axis.axis("off")

    _draw_flow_boxes(axis, [
        (0.3, 4.6, 2.2, 0.9, "原文文件\n抄袭版论文文件", "#eef3fa"),
        (3.0, 4.6, 2.0, 0.9, "main.py\n命令行入口", "#eef3fa"),
        (5.6, 4.6, 2.2, 0.9, "cli.py\n参数校验 + 异常兜底", "#eef3fa"),
        (8.3, 4.6, 1.5, 0.9, "答案文件\n保留两位小数", "#fdeee8"),
        (0.3, 2.9, 2.2, 0.9, "errors.py\n异常体系", "#f3eef7"),
        (3.0, 2.9, 2.0, 0.9, "core.load_text\n编码识别 + 读取", "#e7f0e6"),
        (5.6, 2.9, 2.2, 0.9, "core.normalize\nNFKC + 小写 + 分隔符", "#e7f0e6"),
        (8.3, 2.9, 1.5, 0.9, "core\nextract_tokens\n中文 bigram / 英文词", "#e7f0e6"),
        (5.6, 1.2, 2.2, 0.9, "core.duplicate_rate\n命中特征 / 抄袭版特征", "#fdeee8"),
        (8.3, 1.2, 1.5, 0.9, "core.analyze\n统计 + 结果对象", "#e7f0e6"),
    ])

    for start, end in (
        ((2.5, 5.05), (3.0, 5.05)),
        ((5.0, 5.05), (5.6, 5.05)),
        ((7.8, 5.05), (8.3, 5.05)),
        ((6.7, 4.6), (6.7, 3.8)),
        ((5.0, 3.35), (5.6, 3.35)),
        ((7.8, 3.35), (8.3, 3.35)),
        ((8.9, 2.9), (8.9, 2.1)),
        ((9.05, 1.65), (9.05, 1.2)),
        ((8.3, 1.65), (7.8, 1.65)),
        ((4.0, 2.9), (4.0, 4.6)),
        ((1.4, 3.8), (1.4, 4.6)),
    ):
        _draw_arrow(axis, start, end)

    axis.text(1.5, 5.75, "命令行参数（3 个绝对路径）", fontsize=9, ha="left", color="#5a6b7d")
    axis.text(1.5, 2.55, "被所有步骤共用的异常类型", fontsize=9, ha="left", color="#5a6b7d")
    axis.text(6.9, 3.45, "规范化后的文本", fontsize=9, ha="left", color="#5a6b7d")
    axis.set_title("图 1  论文查重程序的文件划分与数据流", fontsize=13, pad=12)
    path = IMAGE_DIR / "fig1-flow.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def figure_performance(before: str, after: str) -> Path:
    """绘制改进前后的耗时与函数调用次数对比。"""
    labels = ["改进前\n(逐字符构造特征)", "改进后\n(码位元组 + 批量计数)"]
    wall = [parse_wall_time(before), parse_wall_time(after)]
    calls = [parse_call_count(before) / 1000, parse_call_count(after) / 1000]

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.4))
    _draw_bar_panel(
        axes[0], labels, wall, BarPanel("46 万字文档的平均耗时", "秒", _COLOR_AFTER, ".3f")
    )
    _draw_bar_panel(
        axes[1], labels, calls, BarPanel("cProfile 记录的函数调用次数", "千次", _COLOR_ACCENT, ",.0f")
    )
    fig.suptitle("图 2  性能分析工具定位瓶颈并验证改进效果", fontsize=13)
    path = IMAGE_DIR / "fig2-performance.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def _draw_bar_panel(axis, labels: List[str], values: List[float], panel: BarPanel) -> None:
    """画一组"改进前 / 改进后"的对比柱状图。"""
    bars = axis.bar(labels, values, color=[_COLOR_BEFORE, panel.color], width=0.55)
    axis.set_title(panel.title, fontsize=12)
    axis.set_ylabel(panel.unit)
    axis.grid(axis="y", linestyle=":", alpha=0.5)
    axis.set_axisbelow(True)
    for rect, value in zip(bars, values):
        axis.text(
            rect.get_x() + rect.get_width() / 2,
            value,
            format(value, panel.number_format),
            ha="center",
            va="bottom",
            fontsize=10,
        )
    axis.set_ylim(0, max(values) * 1.25)


def figure_hotspots(before: str, after: str) -> Path:
    """绘制热点函数在改进前后的耗时对比。"""
    hot_before = dict(parse_hotspots(before, limit=6))
    hot_after = dict(parse_hotspots(after, limit=6))
    names = list(dict.fromkeys([*hot_before, *hot_after]))[:7]

    fig, axis = plt.subplots(figsize=(9.6, 4.8))
    positions = range(len(names))
    height = 0.38
    axis.barh(
        [pos + height / 2 for pos in positions],
        [hot_before.get(name, 0) for name in names],
        height=height,
        color=_COLOR_BEFORE,
        label="改进前",
    )
    axis.barh(
        [pos - height / 2 for pos in positions],
        [hot_after.get(name, 0) for name in names],
        height=height,
        color=_COLOR_AFTER,
        label="改进后",
    )
    axis.set_yticks(list(positions))
    axis.set_yticklabels(names, fontsize=10)
    axis.invert_yaxis()
    axis.set_xlabel("cProfile tottime（秒，46 万字两篇文档单次对比）")
    axis.grid(axis="x", linestyle=":", alpha=0.5)
    axis.set_axisbelow(True)
    axis.legend()
    axis.set_title("图 3  消耗最大的函数（cProfile 输出，按 tottime 排序）", fontsize=13)
    path = IMAGE_DIR / "fig3-hotspots.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def figure_coverage(coverage_text: str) -> Path:
    """绘制各模块覆盖率。"""
    rows = parse_coverage(coverage_text)
    names = [name.replace(".py", "") for name, _ in rows]
    values = [value for _, value in rows]
    colors = [_COLOR_ACCENT if name == "总体" else _COLOR_AFTER for name in names]

    fig, axis = plt.subplots(figsize=(9.6, 4.2))
    bars = axis.bar(names, values, color=colors, width=0.55)
    axis.set_ylabel("覆盖率（语句 + 分支）%")
    axis.set_ylim(0, 115)
    axis.grid(axis="y", linestyle=":", alpha=0.5)
    axis.set_axisbelow(True)
    for rect, value in zip(bars, values):
        axis.text(
            rect.get_x() + rect.get_width() / 2,
            value + 2,
            f"{value:.0f}%",
            ha="center",
            fontsize=10,
        )
    axis.set_title("图 4  单元测试覆盖率（coverage.py：pytest 共 59 个用例）", fontsize=13)
    path = IMAGE_DIR / "fig4-coverage.png"
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> int:
    """生成全部图表。"""
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    setup_font()
    before = read_text(EVIDENCE_DIR / "performance-before.txt")
    after = read_text(EVIDENCE_DIR / "performance-after.txt")
    coverage_text = read_text(EVIDENCE_DIR / "coverage.txt")

    for path in (
        figure_flow(),
        figure_performance(before, after),
        figure_hotspots(before, after),
        figure_coverage(coverage_text),
    ):
        print(f"已生成 {path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
