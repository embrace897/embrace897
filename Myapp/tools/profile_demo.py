# -*- coding: utf-8 -*-
"""效能分析脚本：用 cProfile 统计生成一万道题时各函数的耗时。

运行方式（项目根目录下）::

    python tools/profile_demo.py
    python tools/profile_demo.py -n 10000 -r 100 -t 10

参数 ``-t`` 表示列出耗时最长的前 N 个函数。把输出截图或复制到博客的
"效能分析" 一节即可。
"""

from __future__ import annotations

import argparse
import cProfile
import os
import pstats
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from myapp.generator import generate_problems  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="四则运算出题程序效能分析")
    parser.add_argument("-n", dest="count", type=int, default=10000)
    parser.add_argument("-r", dest="value_range", type=int, default=100)
    parser.add_argument("-t", dest="top", type=int, default=10, help="显示前 N 个热点函数")
    args = parser.parse_args()

    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    problems, warning = generate_problems(args.count, args.value_range, seed=2026)
    profiler.disable()
    elapsed = time.perf_counter() - start

    print("生成题目数：%d，范围 -r：%d" % (len(problems), args.value_range))
    print("总耗时：%.3f 秒（平均 %.3f 毫秒/题）" % (elapsed, elapsed * 1000 / max(1, len(problems))))
    if warning:
        print("警告：%s" % warning)
    print("-" * 72)
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative").print_stats(args.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
