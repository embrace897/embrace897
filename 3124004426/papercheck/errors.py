"""论文查重程序的异常体系。

所有的自定义异常都继承自 :class:`PaperCheckError`，并携带一个 ``exit_code``
属性：命令行入口捕获异常后，用它作为进程退出码，保证程序不会以
Python 回溯（traceback）的方式崩溃退出。
"""


class PaperCheckError(Exception):
    """所有自定义异常的基类。

    Attributes:
        exit_code: 程序终止时返回给操作系统的退出码。0 表示"输入合法但
            结果退化"，非 0 表示"输入或环境不满足要求"。
    """

    exit_code = 1


class ArgumentError(PaperCheckError):
    """命令行参数的个数或内容不合法。"""

    exit_code = 2


class InputFileError(PaperCheckError):
    """原文或抄袭版论文文件不存在、不是普通文件或无法读取。"""

    exit_code = 3


class EncodingDetectionError(PaperCheckError):
    """尝试了所有候选编码后仍然无法把文件内容解码成文本。"""

    exit_code = 4


class EmptyDocumentError(PaperCheckError):
    """文档（通常是抄袭版论文）中没有任何有效特征。

    空文档属于"合法但退化"的输入：调用方捕获该异常后按重复率 0.00 处理，
    因此退出码为 0，避免评测时因为这类边界输入被判定为异常退出。
    """

    exit_code = 0


class OutputFileError(PaperCheckError):
    """答案文件的路径不可写（例如路径被目录占用或没有写权限）。"""

    exit_code = 5
