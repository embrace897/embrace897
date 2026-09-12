"""论文查重算法包。

模块划分::

    core   读取文件、规范化文本、提取特征、计算重复率（核心算法）
    cli    解析命令行参数、处理异常并把答案写入文件
    errors 自定义异常体系

包内不依赖任何第三方库，只需要 Python 3.8+ 的标准库。
"""

from papercheck.core import Report, analyze, duplicate_rate, extract_tokens, load_text
from papercheck.core import normalize, token_count, write_answer
from papercheck.errors import (
    ArgumentError,
    EmptyDocumentError,
    EncodingDetectionError,
    InputFileError,
    OutputFileError,
    PaperCheckError,
)

__all__ = [
    "ArgumentError",
    "EmptyDocumentError",
    "EncodingDetectionError",
    "InputFileError",
    "OutputFileError",
    "PaperCheckError",
    "Report",
    "analyze",
    "duplicate_rate",
    "extract_tokens",
    "load_text",
    "normalize",
    "token_count",
    "write_answer",
]

__version__ = "1.0.0"
