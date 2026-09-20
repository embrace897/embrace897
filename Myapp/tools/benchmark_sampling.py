# -*- coding: utf-8 -*-
"""性能对比脚本：采样取值时"浮点二分快路径"与"直接用 Fraction 二分"的差异。

运行方式（项目根目录下）::

    python tools/benchmark_sampling.py

博客的"效能分析"一节可以直接引用这里的数字，说明改进思路与效果。
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from myapp.generator import ProblemGenerator, generate_problems  # noqa: E402


def run_once(count: int, value_range: int, fast: bool) -> float:
    ProblemGenerator.USE_FLOAT_FASTPATH = fast
    start = time.perf_counter()
    generate_problems(count, value_range, seed=2026)
    elapsed = time.perf_counter() - start
    return elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="采样性能对比")
    parser.add_argument("-n", dest="count", type=int, default=10000)
    parser.add_argument("-r", dest="value_range", type=int, default=100)
    parser.add_argument("--repeat", type=int, default=3, help="每种方式重复次数，取最快一次")
    args = parser.parse_args()

    results = {}
    for label, fast in (("Fraction 二分（慢路径）", False), ("浮点二分 + 精确修正（快路径）", True)):
        best = min(run_once(args.count, args.value_range, fast) for _ in range(args.repeat))
        results[label] = best
        print("%-28s 生成 %d 道题耗时 %.3f 秒" % (label, args.count, best))

    slow = results["Fraction 二分（慢路径）"]
    fast = results["浮点二分 + 精确修正（快路径）"]
    print("-" * 60)
    print("提速约 %.2f 倍（%.3f 秒 -> %.3f 秒）" % (slow / fast, slow, fast))
    return 0


if __name__ == "__main__":
    sys.exit(main())
