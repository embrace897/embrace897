# -*- coding: utf-8 -*-
"""批改模块：读取题目文件与答案文件，统计对错并写出 Grade.txt。

对应需求 9，命令行形如::

    Myapp.exe -e Exercises.txt -a Answers.txt

输出::

    Correct: 5 (1, 3, 5, 7, 9)
    Wrong: 5 (2, 4, 6, 8, 10)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from .expression import parse_expression
from .values import parse_value

# 行首的题号，例如 "1. " / "1、" / "1:" / "1)"
_NUMBER_PREFIX_RE = re.compile(r"^\s*\d+\s*[.、,，:：)）]\s*")


def strip_number(line: str) -> str:
    """去掉一行开头的题号，只留下题目（或答案）本体。"""
    return _NUMBER_PREFIX_RE.sub("", line.strip())


def read_lines(path: str) -> List[str]:
    """按行读取文本文件，忽略空行。"""
    content = Path(path).read_text(encoding="utf-8")
    return [line for line in content.splitlines() if line.strip()]


def grade_lines(exercise_lines: List[str], answer_lines: List[str]) -> Tuple[List[int], List[int]]:
    """逐题比对，返回 (答对的题号列表, 答错/未答的题号列表)。"""
    if len(exercise_lines) != len(answer_lines):
        raise ValueError(
            "题目文件有 %d 道题，答案文件有 %d 行，两者数量不一致"
            % (len(exercise_lines), len(answer_lines))
        )

    correct: List[int] = []
    wrong: List[int] = []
    for index, (exercise_line, answer_line) in enumerate(
        zip(exercise_lines, answer_lines), start=1
    ):
        exercise_text = strip_number(exercise_line)
        # 题目形如 "1 + 2 × 3 = "，等号右边是留给答题者的空白
        exercise_text = exercise_text.split("=")[0]
        try:
            expected = parse_expression(exercise_text).value
        except ValueError as error:
            raise ValueError("第 %d 行的题目无法解析：%s" % (index, error)) from None

        answer_text = strip_number(answer_line)
        # 允许"学生直接在题目文件的等号后面写答案"，例如 "1. 9 + 6 = 15"
        if "=" in answer_text:
            answer_text = answer_text.rsplit("=", 1)[1]
        try:
            actual = parse_value(answer_text)
        except ValueError:
            wrong.append(index)  # 答案写得无法识别，按答错处理
            continue

        if actual == expected:
            correct.append(index)
        else:
            wrong.append(index)
    return correct, wrong


def format_ids(numbers: List[int]) -> str:
    """把题号列表格式化成 ``(1, 3, 5)``；为空时给出 ``()``。"""
    if not numbers:
        return "()"
    return "(%s)" % ", ".join(str(number) for number in numbers)


def build_grade_text(correct: List[int], wrong: List[int]) -> str:
    return "Correct: %d %s\nWrong: %d %s\n" % (
        len(correct),
        format_ids(correct),
        len(wrong),
        format_ids(wrong),
    )


def grade_files(
    exercise_path: str, answer_path: str, output_path: str = "Grade.txt"
) -> Tuple[List[int], List[int]]:
    """批改两个文件，并把统计结果写入 ``output_path``。"""
    correct, wrong = grade_lines(read_lines(exercise_path), read_lines(answer_path))
    Path(output_path).write_text(build_grade_text(correct, wrong), encoding="utf-8")
    return correct, wrong
