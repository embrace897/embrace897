"""性能分析脚本：生成大文档并用 cProfile 统计耗时瓶颈。

用法（在项目根目录下）::

    python tools/profile_runner.py --size 500000

脚本分两段运行：先用**不开启采样器**的方式测真实墙钟时间（cProfile 会对每次函数
调用插桩，混在一起测会得出错误结论），再单独跑一次带采样的调用取函数级数据。
"""

import argparse
import cProfile
import io
import pstats
import random
import sys
import time
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 上面的 sys.path 调整让脚本可以直接运行，因此这里的导入位置必须在后。
from papercheck.core import analyze  # pylint: disable=wrong-import-position

DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_FILE = DATA_DIR / "orig.txt"

#: 抄袭版的改动比例：每 10 个字符改写 1 个，模拟"改动型抄袭"。
MUTATION_RATE = 10

_REPLACEMENTS = {"的": "之", "了": "过", "是": "为", "在": "于", "和": "与"}

#: 重复测量次数，取最快的一次以减小系统抖动的影响。
REPEAT = 3


def build_big_pair(size: int) -> Tuple[Path, Path]:
    """生成指定规模的原文与抄袭版文档。

    Args:
        size: 原文的目标字符数。

    Returns:
        ``(原文路径, 抄袭版路径)``。
    """
    base = SAMPLE_FILE.read_text(encoding="utf-8").replace("\n", "")
    repeated = (base * (size // len(base) + 1))[:size]

    random.seed(20240910)
    chars: List[str] = list(repeated)
    for index in range(0, len(chars), MUTATION_RATE):
        chars[index] = _REPLACEMENTS.get(chars[index], "新")

    origin_path = DATA_DIR / "big_orig.txt"
    copy_path = DATA_DIR / "big_copy.txt"
    origin_path.write_text(repeated, encoding="utf-8")
    copy_path.write_text("".join(chars), encoding="utf-8")
    return origin_path, copy_path


def main() -> int:
    """命令行入口。"""
    parser = argparse.ArgumentParser(description="论文查重程序性能分析")
    parser.add_argument("--size", type=int, default=500_000, help="生成的原文规模（字符数）")
    args = parser.parse_args()

    origin_path, copy_path = build_big_pair(args.size)

    elapsed = []
    report = None
    for _ in range(REPEAT):
        start = time.perf_counter()
        report = analyze(origin_path, copy_path)
        elapsed.append(time.perf_counter() - start)

    print(f"原文 {report.origin_chars} 字 / {report.origin_tokens} 个特征")
    print(f"抄袭版 {report.copy_chars} 字 / {report.copy_tokens} 个特征，重复率 {report.rate:.2f}")
    print(f"最快耗时 {min(elapsed):.3f} s（{REPEAT} 次）\n")

    profiler = cProfile.Profile()
    profiler.runcall(analyze, origin_path, copy_path)
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("tottime").print_stats(10)
    print(stream.getvalue())
    return 0


if __name__ == "__main__":
    sys.exit(main())
