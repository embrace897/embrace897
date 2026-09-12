"""命令行接口：参数解析、查重调用、异常兜底。"""

import sys
from typing import List, Optional, Sequence, Tuple

from papercheck.core import analyze, write_answer
from papercheck.errors import ArgumentError, PaperCheckError

USAGE = "python main.py <原文文件> <抄袭版论文文件> <答案文件>"

_HELP_FLAGS = ("-h", "--help", "/?")


def parse_args(argv: Sequence[str]) -> Tuple[str, str, str]:
    """解析命令行参数。

    Args:
        argv: 除程序名以外的命令行参数。

    Returns:
        ``(原文路径, 抄袭版路径, 答案文件路径)``。

    Raises:
        ArgumentError: 参数个数不为 3，或者某个参数为空字符串。
    """
    if len(argv) != 3:
        raise ArgumentError(
            f"需要 3 个参数（原文文件、抄袭版论文文件、答案文件），实际收到 {len(argv)} 个；"
            f"用法：{USAGE}"
        )
    origin_path, copy_path, answer_path = (item.strip() for item in argv)
    if not origin_path or not copy_path or not answer_path:
        raise ArgumentError(f"参数不能为空字符串；用法：{USAGE}")
    return origin_path, copy_path, answer_path


def main(argv: Optional[List[str]] = None) -> int:
    """程序主函数。

    Args:
        argv: 命令行参数列表；``None`` 表示使用 ``sys.argv``。

    Returns:
        进程退出码：0 表示成功，非 0 表示输入或环境不满足要求。
    """
    arguments = list(sys.argv[1:] if argv is None else argv)
    if any(flag in arguments for flag in _HELP_FLAGS):
        print(USAGE)
        return 0

    try:
        origin_path, copy_path, answer_path = parse_args(arguments)
        report = analyze(origin_path, copy_path)
        answer_file = write_answer(report, answer_path)
    except PaperCheckError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return exc.exit_code

    for warning in report.warnings:
        print(f"[警告] {warning}", file=sys.stderr)
    print(
        f"重复率 {report.rate:.2f}（原文 {report.origin_tokens} 个特征，"
        f"抄袭版 {report.copy_tokens} 个特征）-> {answer_file}"
    )
    return 0
