# -*- coding: utf-8 -*-
"""算术表达式：结点定义、求值、去重规范形、最少括号渲染、字符串解析。

关于"重复题目"的判定（需求 6）
------------------------------
题目规定：两道题如果能通过**有限次交换 + 和 × 的左右操作数**变成同一道题，
就判定为重复。也就是说等价关系是"表达式树在交换律下同构"，**不含结合律**。
因此 :meth:`Expr.canonical_key` 的做法是：

* 递归求出左右子树的规范形；
* 若当前结点是 + 或 ×，就把两个孩子的规范形**排序后拼接**（交换律生效）；
* 否则按左右顺序拼接（- 和 ÷ 不可交换）。

这样 ``3+(2+1)`` 与 ``1+2+3``（即 ``(1+2)+3``）会得到同一个 key，判为重复；
而 ``1+2+3`` 与 ``3+2+1``（即 ``(3+2)+1``）的 key 不同，判为不重复，
与题目给出的例子完全一致。
"""

from __future__ import annotations

from fractions import Fraction
import re
from typing import List

from .values import format_value, parse_value

OPERATORS = ("+", "-", "×", "÷")
PRECEDENCE = {"+": 1, "-": 1, "×": 2, "÷": 2}
COMMUTATIVE = ("+", "×")

_NUMBER_PATTERN = r"\d+['’‘′´`]\d+/\d+|\d+/\d+|\d+"
_TOKEN_RE = re.compile(r"\s*(%s|[()+\-×÷*/])" % _NUMBER_PATTERN)


class Expr:
    """表达式结点基类。"""

    __slots__ = ()

    value: Fraction

    def operator_count(self) -> int:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    def canonical_key(self) -> str:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    def render(self) -> str:  # pragma: no cover - 由子类实现
        raise NotImplementedError

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return "<%s %s>" % (type(self).__name__, self.render())


class Num(Expr):
    """叶子结点：自然数或真分数（含带分数写法）。"""

    __slots__ = ("value",)

    def __init__(self, value: Fraction) -> None:
        self.value = Fraction(value)

    def operator_count(self) -> int:
        return 0

    def canonical_key(self) -> str:
        # 用分子/分母表示，保证 1/2 与 2/4 这类等值分数得到同一个 key
        return "N%d/%d" % (self.value.numerator, self.value.denominator)

    def render(self) -> str:
        return format_value(self.value)


class BinOp(Expr):
    """内部结点：一次四则运算。"""

    __slots__ = ("op", "left", "right", "value")

    def __init__(self, op: str, left: Expr, right: Expr) -> None:
        if op not in OPERATORS:
            raise ValueError("不支持的运算符：%r" % (op,))
        self.op = op
        self.left = left
        self.right = right
        self.value = self._evaluate()

    def _evaluate(self) -> Fraction:
        left_value = self.left.value
        right_value = self.right.value
        if self.op == "+":
            return left_value + right_value
        if self.op == "-":
            return left_value - right_value
        if self.op == "×":
            return left_value * right_value
        if right_value == 0:
            raise ZeroDivisionError("除数不能为 0")
        return left_value / right_value

    def operator_count(self) -> int:
        return 1 + self.left.operator_count() + self.right.operator_count()

    def canonical_key(self) -> str:
        left_key = self.left.canonical_key()
        right_key = self.right.canonical_key()
        if self.op in COMMUTATIVE and right_key < left_key:
            left_key, right_key = right_key, left_key
        return "%s(%s,%s)" % (self.op, left_key, right_key)

    def render(self) -> str:
        return "%s %s %s" % (
            self._render_child(self.left, is_right=False),
            self.op,
            self._render_child(self.right, is_right=True),
        )

    def _render_child(self, child: Expr, is_right: bool) -> str:
        """按优先级补最少的括号，保证"一棵树只对应一种写法"。

        这样既能去掉多余括号（``(1+2)+3`` 写成 ``1 + 2 + 3``），
        又不会把两棵不同的树写成同一个字符串（``1+(2+3)`` 必须带括号）。
        """
        text = child.render()
        if not isinstance(child, BinOp):
            return text
        child_precedence = PRECEDENCE[child.op]
        self_precedence = PRECEDENCE[self.op]
        if child_precedence < self_precedence:
            return "(%s)" % text
        if child_precedence == self_precedence and is_right:
            return "(%s)" % text
        return text


def parse_expression(text: str) -> Expr:
    """把 ``1 + 2 × (3 - 1/2)`` 这类字符串解析成表达式树。

    支持 ``× ÷`` 以及键盘上的 ``* /``，支持括号与多层嵌套。
    """
    tokens = _tokenize(text)
    if not tokens:
        raise ValueError("表达式为空")
    return _Parser(tokens).parse()


def _tokenize(text: str) -> List[str]:
    tokens: List[str] = []
    position = 0
    length = len(text)
    while position < length:
        match = _TOKEN_RE.match(text, position)
        if match is None:
            if text[position].isspace():
                position += 1
                continue
            raise ValueError("无法识别的字符：%r" % (text[position],))
        tokens.append(match.group(1))
        position = match.end()
    return tokens


class _Parser:
    """递归下降解析器：expression -> term -> factor，天然满足左结合。"""

    def __init__(self, tokens: List[str]) -> None:
        self._tokens = tokens
        self._position = 0

    def parse(self) -> Expr:
        node = self._expression()
        if self._position != len(self._tokens):
            raise ValueError("多余的记号：%r" % (self._tokens[self._position],))
        return node

    def _peek(self) -> str:
        if self._position < len(self._tokens):
            return self._tokens[self._position]
        return ""

    def _next(self) -> str:
        token = self._peek()
        if not token:
            raise ValueError("表达式不完整")
        self._position += 1
        return token

    def _expression(self) -> Expr:
        node = self._term()
        while self._peek() in ("+", "-"):
            node = BinOp(self._next(), node, self._term())
        return node

    def _term(self) -> Expr:
        node = self._factor()
        while self._peek() in ("×", "÷", "*", "/"):
            op = self._next()
            node = BinOp({"*": "×", "/": "÷"}.get(op, op), node, self._factor())
        return node

    def _factor(self) -> Expr:
        token = self._peek()
        if token == "(":
            self._next()
            node = self._expression()
            if self._next() != ")":
                raise ValueError("括号不匹配")
            return node
        if not token or token in ("+", "-", "×", "÷", "*", "/", ")"):
            raise ValueError("意外的记号：%r" % (token,))
        self._next()
        return Num(parse_value(token))
