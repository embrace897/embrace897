"""扩展功能：一次把原文与多份抄袭版论文做对比。

基础功能只处理"一篇原文 + 一份抄袭版"，批改作业时往往需要一次性对比多份文档：

    python tools/batch_check.py <原文文件> <抄袭版1> [抄袭版2 ...]

输出一行为一份文档的对比结果；某一篇读取失败时只记录原因，不影响其余文档，
对应单元测试里"文件不存在""编码无法识别"等异常场景。
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 上面的 sys.path 调整让脚本可以直接运行，因此这里的导入位置必须在后。
from papercheck.core import Report, analyze  # pylint: disable=wrong-import-position
from papercheck.errors import PaperCheckError  # pylint: disable=wrong-import-position

HEADERS = ("抄袭版文件", "重复率", "原文特征", "抄袭版特征", "备注")


def _evaluate(origin: str, copies: Sequence[str]) -> List[Tuple[Optional[Report], str]]:
    """对每一份抄袭版文件做查重，把异常转换成一行错误信息。"""
    results: List[Tuple[Optional[Report], str]] = []
    for copy_path in copies:
        try:
            report = analyze(origin, copy_path)
        except PaperCheckError as exc:
            results.append((None, f"跳过（{exc}）"))
        else:
            results.append((report, "；".join(report.warnings)))
    return results


def _display_width(text: str) -> int:
    """估算显示宽度：非 ASCII 字符按两列计算。"""
    return sum(2 if ord(char) > 0x2E80 else 1 for char in text)


def _format_table(rows: Sequence[Sequence[str]]) -> str:
    """把二维数据排版成等宽表格。"""
    widths = [
        max(_display_width(str(row[index])) for row in [HEADERS, *rows])
        for index in range(len(HEADERS))
    ]
    lines = []
    for row in [HEADERS, *rows]:
        cells = [
            str(cell) + " " * (widths[index] - _display_width(str(cell)))
            for index, cell in enumerate(row)
        ]
        lines.append("  ".join(cells))
    return "\n".join(lines)


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="批量论文查重")
    parser.add_argument("origin", help="原文文件路径")
    parser.add_argument("copies", nargs="+", help="一个或多个抄袭版论文路径")
    args = parser.parse_args()

    rows = []
    for copy_path, (report, note) in zip(args.copies, _evaluate(args.origin, args.copies)):
        if report is None:
            rows.append([Path(copy_path).name, "-", "-", "-", note])
        else:
            rows.append(
                [
                    Path(copy_path).name,
                    f"{report.rate:.2f}",
                    report.origin_tokens,
                    report.copy_tokens,
                    note or "-",
                ]
            )

    print(_format_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
