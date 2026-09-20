# -*- coding: utf-8 -*-
"""小学四则运算题目自动生成 / 自动批改命令行程序。

模块划分
--------
* :mod:`myapp.values`     整数、真分数、带分数的解析与格式化
* :mod:`myapp.expression` 表达式树（求值、去重规范形、最少括号渲染、字符串解析）
* :mod:`myapp.generator`  按 ``-r`` 范围随机出题，保证约束与题目互不重复
* :mod:`myapp.grader`     按 ``-e`` / ``-a`` 批改答案并输出 Grade.txt
* :mod:`myapp.cli`        命令行参数解析与三种运行模式的调度
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
