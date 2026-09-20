# -*- coding: utf-8 -*-
"""程序入口，等价于题目中的 Myapp.exe。

直接运行::

    python main.py -n 10 -r 10
    python main.py -e Exercises.txt -a Answers.txt

打包成 exe 后就是::

    Myapp.exe -n 10 -r 10
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from myapp.cli import main  # noqa: E402  (必须在 sys.path 调整之后导入)

if __name__ == "__main__":
    sys.exit(main())
