# -*- coding: utf-8 -*-
"""出题器：随机生成满足全部约束、并且互不重复的四则运算题目。

约束（对应需求 3、4、5、6）
---------------------------
1. 任何子表达式的值都 >= 0（减法要求左操作数不小于右操作数）；
2. 任何除法子表达式的商都是真分数（0 < 商 < 1）；
   若用 ``--div-mode any`` 则放宽为"只要除数不为 0"；
3. 每道题的运算符个数不超过 ``max_operators``（默认 3）；
4. 同一次运行中不出现重复题目（用 :meth:`Expr.canonical_key` 去重）。

实现思路
--------
先随机切分"运算符个数"得到表达式树的形状与各个运算符，再用**带约束的采样**
给叶子填数值。函数 :meth:`ProblemGenerator._build` 接收一个取值区间 ``(lo, hi]``，
自顶向下把约束传给子表达式：

* ``e1 - e2``：先定 ``e1``，再要求 ``e2 <= e1``（计算过程不出现负数）；
* ``e1 ÷ e2``：要求 ``e1 > 0`` 且 ``e2 > e1``（商必然小于 1，即真分数）；
* ``e1 + e2`` / ``e1 × e2``：用上界约束限制孩子，最后统一校验一次。

这样绝大多数随机尝试都能一次成功，少量失败的按次数重试即可，
生成一万道题也是秒级。
"""

from __future__ import annotations

from bisect import bisect_right
from fractions import Fraction
import random
from typing import List, Optional, Sequence, Tuple

from .expression import BinOp, Expr, Num
from .values import build_value_pool

# 严格不等号的余量：取值池中所有数的分母都是有限小的整数，1e-6 足够安全
_EPS = Fraction(1, 10 ** 6)
# 哨兵：表示"除了自然数本身 >= 0 之外没有额外下界"
_UNBOUNDED = Fraction(-1)


class ProblemGenerator:
    """按范围 ``r`` 生成题目。"""

    #: 采样时是否使用"浮点二分 + 精确修正"的快路径。
    #: 关掉它就会退化成直接用 Fraction 做二分，用于性能对比（见 tools/benchmark_sampling.py）。
    USE_FLOAT_FASTPATH = True

    def __init__(
        self,
        r: int,
        max_operators: int = 3,
        div_mode: str = "proper",
        seed: Optional[int] = None,
    ) -> None:
        if r < 1:
            raise ValueError("范围 r 必须是不小于 1 的自然数，当前为 %r" % (r,))
        if max_operators < 1:
            raise ValueError("运算符个数上限至少为 1，当前为 %r" % (max_operators,))
        if div_mode not in ("proper", "any"):
            raise ValueError("div_mode 只能是 'proper' 或 'any'")

        self.r = r
        self.max_operators = int(max_operators)
        self.div_mode = div_mode
        self.naturals, self.fractions = build_value_pool(r)
        # 与取值池一一对应的浮点键，用于快速二分定位
        self._naturals_keys = [float(value) for value in self.naturals]
        self._fractions_keys = [float(value) for value in self.fractions]
        self.max_value = self.naturals[-1] if self.naturals else Fraction(0)
        self._rng = random.Random(seed)
        self._usable_operators = self._pick_usable_operators()

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def new_problem(self, operator_count: Optional[int] = None) -> Optional[Expr]:
        """生成一道题；极端情况下（例如 r=2 时抽到除法）可能返回 None。"""
        if operator_count is None:
            operator_count = self._rng.randint(1, self.max_operators)
        return self._build(operator_count, _UNBOUNDED, None)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------
    def _pick_usable_operators(self) -> Tuple[str, ...]:
        """筛掉当前取值池下不可能出现的运算符（例如 r=2 时无法做除法）。"""
        usable = ["+", "-", "×"]
        positive = [v for v in self.naturals + self.fractions if v > 0]
        if positive and self.max_value > 0 and any(v < self.max_value for v in positive):
            usable.append("÷")
        return tuple(usable)

    def _sample(self, lo_exc: Fraction, hi_inc: Optional[Fraction]) -> Optional[Fraction]:
        """在取值池里随机取一个满足 ``lo_exc < v <= hi_inc`` 的值。

        自然数与真分数各占一半概率，让题目里既有整数也有分数。
        """
        subsets: List[Tuple[Sequence[Fraction], Sequence[float]]] = [
            (self.naturals, self._naturals_keys),
            (self.fractions, self._fractions_keys),
        ]
        if self._rng.random() < 0.5:
            subsets.reverse()
        for subset, keys in subsets:
            if not subset:
                continue
            start = self._first_greater(subset, keys, lo_exc)
            end = len(subset) if hi_inc is None else self._first_greater(subset, keys, hi_inc)
            if end > start:
                return subset[self._rng.randrange(start, end)]
        return None

    @staticmethod
    def _first_greater(
        subset: Sequence[Fraction], keys: Sequence[float], bound: Fraction
    ) -> int:
        """返回第一个大于 ``bound`` 的元素下标（等价于 bisect_right 的严格版本）。

        先用浮点键二分拿到近似位置，再用精确的分数比较向两侧修正。
        由于浮点只是"近似"，修正循环保证了结果与直接用 Fraction 二分完全一致，
        但绝大多数情况下只需要 0~2 次精确比较，这就是性能提升的来源。
        """
        if ProblemGenerator.USE_FLOAT_FASTPATH:
            index = bisect_right(keys, float(bound))
        else:
            index = bisect_right(subset, bound)
        # 修正 1：把下标左移到"左边都 <= bound"的位置
        while index > 0 and subset[index - 1] > bound:
            index -= 1
        # 修正 2：把下标右移到"当前位置的元素 > bound"
        while index < len(subset) and subset[index] <= bound:
            index += 1
        return index

    def _build(
        self,
        operator_count: int,
        lo_exc: Fraction,
        hi_inc: Optional[Fraction],
        tries: int = 8,
    ) -> Optional[Expr]:
        """在取值区间 ``(lo_exc, hi_inc]`` 内生成指定运算符个数的子树。"""
        for _ in range(tries):
            node = self._attempt(operator_count, lo_exc, hi_inc)
            if node is None:
                continue
            value = node.value
            if value > lo_exc and (hi_inc is None or value <= hi_inc):
                return node
        return None

    def _attempt(
        self, operator_count: int, lo_exc: Fraction, hi_inc: Optional[Fraction]
    ) -> Optional[Expr]:
        """尝试构造一棵子树，失败返回 None，由调用方重试。"""
        rng = self._rng
        if operator_count == 0:
            value = self._sample(lo_exc, hi_inc)
            return None if value is None else Num(value)

        left_count = rng.randint(0, operator_count - 1)
        right_count = operator_count - 1 - left_count
        op = rng.choice(self._usable_operators)

        if op == "+":
            # 和 <= hi 时两个加数都不会超过 hi；和 > lo 时让两个加数都 > lo（保守但安全）
            left = self._build(left_count, lo_exc, hi_inc)
            if left is None:
                return None
            right_hi = None if hi_inc is None else hi_inc - left.value
            right = self._build(right_count, lo_exc, right_hi)
            if right is None:
                return None
            return BinOp("+", left, right)

        if op == "-":
            # 需求 3：e1 - e2 >= 0，即 e2 <= e1
            left = self._build(left_count, lo_exc, hi_inc)
            if left is None:
                return None
            if lo_exc > _UNBOUNDED:
                right_hi = min(left.value, left.value - lo_exc - _EPS)
            else:
                right_hi = left.value
            right = self._build(right_count, _UNBOUNDED, right_hi)
            if right is None:
                return None
            return BinOp("-", left, right)

        if op == "×":
            left = self._build(left_count, _UNBOUNDED, hi_inc)
            if left is None:
                return None
            if hi_inc is None or left.value == 0:
                right_hi = None
            else:
                right_hi = hi_inc / left.value
            right = self._build(right_count, _UNBOUNDED, right_hi)
            if right is None:
                return None
            return BinOp("×", left, right)

        # op == "÷"
        right_hi: Optional[Fraction]
        if self.div_mode == "proper":
            # 需求 4：商是真分数，所以 被除数 > 0 且 除数 > 被除数
            left = self._build(left_count, max(lo_exc, Fraction(0)), hi_inc)
            if left is None:
                return None
            right_lo = left.value
            right_hi = None
            if hi_inc is not None:
                if hi_inc <= 0:
                    return None
                right_hi = left.value / hi_inc
            if lo_exc > 0:
                limit = left.value / lo_exc - _EPS
                right_hi = limit if right_hi is None else min(right_hi, limit)
        else:
            left = self._build(left_count, lo_exc, hi_inc)
            if left is None:
                return None
            right_lo = Fraction(0)  # 除数不能为 0
            right_hi = None
            if hi_inc is not None and left.value > 0:
                right_hi = left.value / hi_inc
        right = self._build(right_count, right_lo, right_hi)
        if right is None:
            return None
        return BinOp("÷", left, right)


def generate_problems(
    n: int,
    r: int,
    max_operators: int = 3,
    div_mode: str = "proper",
    seed: Optional[int] = None,
) -> Tuple[List[Expr], Optional[str]]:
    """生成 ``n`` 道互不重复的题目。

    返回 ``(题目列表, 警告信息)``。若取值范围内确实凑不出这么多不重复题目，
    则返回能生成的全部题目，并把原因写进警告信息（例如 ``-r 1`` 时只有 0 可用）。
    """
    if n < 1:
        raise ValueError("题目个数 n 必须是不小于 1 的自然数，当前为 %r" % (n,))

    generator = ProblemGenerator(
        r, max_operators=max_operators, div_mode=div_mode, seed=seed
    )
    problems: List[Expr] = []
    seen = set()

    attempt_limit = max(4000, n * 50)
    stall_limit = max(2000, min(30000, n))
    attempts = 0
    stall = 0

    while len(problems) < n and attempts < attempt_limit and stall < stall_limit:
        attempts += 1
        expr = generator.new_problem()
        if expr is None:
            stall += 1
            continue
        key = expr.canonical_key()
        if key in seen:
            stall += 1
            continue
        seen.add(key)
        problems.append(expr)
        stall = 0

    warning = None
    if len(problems) < n:
        warning = (
            "-r %d 的范围内可用数值太少，搜索到 %d 道互不重复且满足全部约束的题目后，"
            "已经找不到新题目了；本次输出这 %d 道，如需更多请增大 -r 或减小 -n。"
            % (r, len(problems), len(problems))
        )
    return problems, warning
