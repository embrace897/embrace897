"""论文查重程序的命令行入口。

用法（三个参数都是绝对路径，参数之间用空格分隔）::

    python main.py <原文文件> <抄袭版论文文件> <答案文件>

程序从原文文件与抄袭版论文文件中读取文本，计算抄袭版论文相对于原文的
重复率，并把重复率（保留两位小数的浮点数）写入答案文件。
"""

import sys

from papercheck.cli import main

if __name__ == "__main__":
    sys.exit(main())
