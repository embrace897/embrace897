# -*- coding: utf-8 -*-
"""数值工具：自然数 / 真分数 / 带分数的解析、格式化，以及取值池的构造。

约定
----
* 所有有理数统一用 :class:`fractions.Fraction` 表示，运算绝对精确，
  不会出现 ``1/6 + 1/8`` 被算成 0.29 这种浮点误差。
* 对外显示：整数写 ``3``；真分数写 ``3/5``；带分数写 ``2'3/8``
  （题目里给出的 ``2’3/8`` 是同一个意思，读入时两种撇号都接受）。
"""

from __future__ import annotations

from fractions import Fraction
from typing import List, Tuple

# 各种撇号写法：键盘单引号、中文右/左单引号、角分符号、重音符、反引号
_APOSTROPHE_CHARS = "'’‘′´`"


def _strip_blanks(text: str) -> str:
    """去掉普通空格、全角空格和制表符。"""
    return text.replace(" ", "").replace("\u3000", "").replace("\t", "")


def _split_sign(text: str) -> Tuple[int, str]:
    """拆出可选的正负号，返回 (符号, 剩余部分)。"""
    text = text.strip()
    if text.startswith("+"):
        return 1, text[1:]
    if text.startswith("-"):
        return -1, text[1:]
    return 1, text


def parse_value(text: str) -> Fraction:
    """把 ``3`` / ``3/5`` / ``2'3/8`` 这类写法转成 :class:`Fraction`。

    解析失败时抛出 :class:`ValueError`，并带上原始文本方便定位问题。
    """
    sign, body = _split_sign(_strip_blanks(text))
    if not body:
        raise ValueError("不完整的数值：%r" % (text,))

    # 带分数：整数'真分数，例如 2'3/8
    for ch in _APOSTROPHE_CHARS:
        if ch in body:
            whole_text, _, frac_text = body.partition(ch)
            if "/" not in frac_text:
                raise ValueError("带分数要写成 整数'真分数 的形式：%r" % (text,))
            whole = _parse_integer(whole_text, text)
            frac = _parse_simple_fraction(frac_text, text)
            if not 0 <= frac < 1:
                raise ValueError("带分数的小数部分必须是真分数：%r" % (text,))
            return sign * (whole + frac)

    # 真分数：分子/分母
    if "/" in body:
        return sign * _parse_simple_fraction(body, text)

    # 自然数
    return Fraction(sign * _parse_integer(body, text), 1)


def _parse_integer(text: str, origin: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ValueError("不是合法的整数：%r" % (origin,)) from None


def _parse_simple_fraction(text: str, origin: str) -> Fraction:
    numerator_text, sep, denominator_text = text.partition("/")
    if not sep:
        raise ValueError("不是合法的分数：%r" % (origin,))
    numerator = _parse_integer(numerator_text, origin)
    denominator = _parse_integer(denominator_text, origin)
    if denominator == 0:
        raise ValueError("分母不能为 0：%r" % (origin,))
    return Fraction(numerator, denominator)


def format_value(value: Fraction, apostrophe: str = "'") -> str:
    """把有理数格式化成题目要求的写法。

    >>> format_value(Fraction(3))
    '3'
    >>> format_value(Fraction(3, 5))
    '3/5'
    >>> format_value(Fraction(19, 8))
    "2'3/8"
    """
    value = Fraction(value)
    if value < 0:
        return "-" + format_value(-value, apostrophe)
    if value.denominator == 1:
        return str(value.numerator)
    whole, remainder = divmod(value.numerator, value.denominator)
    if whole == 0:
        return "%d/%d" % (remainder, value.denominator)
    return "%d%s%d/%d" % (whole, apostrophe, remainder, value.denominator)


def build_value_pool(r: int) -> Tuple[List[Fraction], List[Fraction]]:
    """构造取值范围小于 ``r`` 的取值池。

    返回 ``(自然数列表, 真分数列表)``，两个列表都按大小升序排列，
    方便后面用二分查找随机取样。

    * 自然数：``0, 1, ..., r-1``
    * 真分数：分母 ``< r``、分子 ``< 分母``，且都为最简写法，
      例如 r=10 时有 1/2、1/3、2/3、...、8/9
    """
    if r < 1:
        raise ValueError("范围 r 必须是不小于 1 的自然数，当前为 %r" % (r,))

    naturals = [Fraction(i, 1) for i in range(r)]
    fractions = sorted({Fraction(n, d) for d in range(2, r) for n in range(1, d)})
    return naturals, fractions
