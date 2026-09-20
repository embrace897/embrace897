# -*- coding: utf-8 -*-
"""命令行入口：解析参数，并按"生成题目"或"批改答案"两种模式执行。

三种用法::

    Myapp.exe -n 10 -r 10                      # 生成 10 道 10 以内的题目
    Myapp.exe -n 10000 -r 100                  # 支持一次生成一万道
    Myapp.exe -e Exercises.txt -a Answers.txt  # 批改
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .expression import Expr
from .generator import generate_problems
from .grader import format_ids, grade_files
from .values import format_value

EXERCISE_FILE = "Exercises.txt"
ANSWER_FILE = "Answers.txt"
GRADE_FILE = "Grade.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Myapp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="小学四则运算题目自动生成 / 自动批改程序",
        epilog=(
            "示例：\n"
            "  Myapp.exe -n 10 -r 10\n"
            "  Myapp.exe -n 10000 -r 100\n"
            "  Myapp.exe -e Exercises.txt -a Answers.txt\n"
        ),
    )
    parser.add_argument(
        "-n",
        dest="count",
        type=int,
        default=10,
        metavar="<题目个数>",
        help="生成题目的个数，默认为 10",
    )
    parser.add_argument(
        "-r",
        dest="value_range",
        type=int,
        default=None,
        metavar="<范围>",
        help="题目中数值（自然数、真分数及其分母）的范围，数值都小于该值；必须给定",
    )
    parser.add_argument(
        "-e",
        dest="exercise_file",
        metavar="<题目文件>",
        help="要批改的题目文件，需与 -a 同时使用",
    )
    parser.add_argument(
        "-a",
        dest="answer_file",
        metavar="<答案文件>",
        help="要批改的答案文件，需与 -e 同时使用",
    )
    parser.add_argument(
        "-o",
        dest="output_dir",
        default=".",
        metavar="<输出目录>",
        help="输出目录，默认为执行程序的当前目录",
    )
    parser.add_argument(
        "--max-operators",
        dest="max_operators",
        type=int,
        default=3,
        metavar="<个数>",
        help="每道题运算符个数上限，默认 3（需求要求不超过 3）",
    )
    parser.add_argument(
        "--div-mode",
        dest="div_mode",
        choices=("proper", "any"),
        default="proper",
        help="除法约束：proper=商必须是真分数（默认，符合需求 4）；any=只要求除数不为 0",
    )
    parser.add_argument(
        "--apostrophe",
        dest="apostrophe",
        choices=("ascii", "unicode"),
        default="ascii",
        help="带分数的撇号风格：ascii 输出 2'3/8，unicode 输出题目原文的 2’3/8",
    )
    parser.add_argument(
        "--seed",
        dest="seed",
        type=int,
        default=None,
        metavar="<整数>",
        help="随机种子，指定后每次生成的题目完全相同（便于复现与测试）",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="Myapp %s" % __version__,
        help="显示版本号",
    )
    return parser


def _configure_stdout() -> None:
    """让 Windows 控制台也能正常打印中文与 × ÷ 等符号。"""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:  # pragma: no cover - 只在真实终端里生效
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main(argv: Optional[List[str]] = None) -> int:
    _configure_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.exercise_file or args.answer_file:
        return _run_grade(args, parser)
    return _run_generate(args, parser)


def _run_generate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    # 需求 2：-r 必须给定，否则报错并给出帮助信息
    if args.value_range is None:
        print("错误：必须使用 -r 参数指定数值范围。", file=sys.stderr)
        print("", file=sys.stderr)
        parser.print_help(sys.stderr)
        return 2
    if args.count < 1:
        print("错误：-n 必须是不小于 1 的自然数，当前为 %r。" % args.count, file=sys.stderr)
        return 2
    if args.value_range < 1:
        print(
            "错误：-r 必须是不小于 1 的自然数，当前为 %r。" % args.value_range,
            file=sys.stderr,
        )
        return 2
    if args.max_operators < 1:
        print(
            "错误：--max-operators 必须是不小于 1 的自然数，当前为 %r。"
            % args.max_operators,
            file=sys.stderr,
        )
        return 2

    try:
        problems, warning = generate_problems(
            args.count,
            args.value_range,
            max_operators=args.max_operators,
            div_mode=args.div_mode,
            seed=args.seed,
        )
    except ValueError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    exercise_path = output_dir / EXERCISE_FILE
    answer_path = output_dir / ANSWER_FILE
    _write_file(exercise_path, _exercise_lines(problems, args.apostrophe))
    _write_file(answer_path, _answer_lines(problems, args.apostrophe))

    print("已生成 %d 道题目：" % len(problems))
    print("  题目文件：%s" % exercise_path.resolve())
    print("  答案文件：%s" % answer_path.resolve())
    if warning:
        print("提示：%s" % warning, file=sys.stderr)
        return 0
    return 0


def _run_grade(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not (args.exercise_file and args.answer_file):
        print("错误：批改模式必须同时给出 -e 和 -a 两个参数。", file=sys.stderr)
        print("", file=sys.stderr)
        parser.print_help(sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    grade_path = output_dir / GRADE_FILE
    try:
        correct, wrong = grade_files(args.exercise_file, args.answer_file, str(grade_path))
    except FileNotFoundError as error:
        print("错误：找不到文件 %s" % error.filename, file=sys.stderr)
        return 2
    except ValueError as error:
        print("错误：%s" % error, file=sys.stderr)
        return 2

    print("批改完成：答对 %d 道，答错 %d 道。" % (len(correct), len(wrong)))
    print("  答对题号：%s" % _summarize_ids(correct))
    print("  答错题号：%s" % _summarize_ids(wrong))
    print("  统计文件：%s" % grade_path.resolve())
    return 0


def _summarize_ids(numbers: List[int], limit: int = 20) -> str:
    """控制台里只显示前若干个题号，避免一万道题时刷屏（Grade.txt 里是完整列表）。"""
    if len(numbers) <= limit:
        return format_ids(numbers)
    head = format_ids(numbers[:limit])
    return "%s ...（共 %d 道，完整列表见 Grade.txt）" % (head[:-1] + ", ...)", len(numbers))


def _exercise_lines(problems: List[Expr], apostrophe: str) -> List[str]:
    """题目行格式为 ``序号. 表达式 = ``（等号后面留空给答题者填写）。"""
    return [
        "%d. %s = " % (index, _convert_apostrophe(problem.render(), apostrophe))
        for index, problem in enumerate(problems, start=1)
    ]


def _answer_lines(problems: List[Expr], apostrophe: str) -> List[str]:
    return [
        "%d. %s" % (index, _convert_apostrophe(format_value(problem.value), apostrophe))
        for index, problem in enumerate(problems, start=1)
    ]


def _convert_apostrophe(text: str, apostrophe: str) -> str:
    """带分数分隔符默认用键盘单引号，需要时转换成题目原文的 ’。"""
    if apostrophe == "unicode":
        return text.replace("'", "’")
    return text


def _write_file(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
