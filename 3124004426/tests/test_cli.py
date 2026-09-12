"""命令行入口的单元测试（含真实的子进程调用）。"""

import subprocess
import sys
from pathlib import Path

import pytest

from papercheck.cli import USAGE, main, parse_args
from papercheck.errors import ArgumentError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ORIGIN = DATA_DIR / "orig.txt"
COPY = DATA_DIR / "orig_add.txt"


def test_parse_args_returns_three_paths():
    """三个参数按顺序解析为原文、抄袭版、答案文件。"""
    assert parse_args([" a.txt ", "b.txt", "c.txt"]) == ("a.txt", "b.txt", "c.txt")


def test_parse_args_rejects_wrong_count():
    """参数个数不是 3 时抛出参数异常。"""
    with pytest.raises(ArgumentError, match="需要 3 个参数"):
        parse_args(["a.txt", "b.txt"])


def test_parse_args_rejects_empty_argument():
    """参数是空字符串时（例如脚本里变量没赋上）同样报错。"""
    with pytest.raises(ArgumentError, match="不能为空字符串"):
        parse_args(["", "b.txt", "c.txt"])


def test_main_writes_answer_file(tmp_path):
    """正常输入下返回 0 并写出答案文件。"""
    answer = tmp_path / "ans.txt"
    assert main([str(ORIGIN), str(COPY), str(answer)]) == 0
    assert answer.read_text(encoding="utf-8").strip() == "0.93"


def test_main_reports_argument_error(capsys):
    """参数个数错误时返回退出码 2，并向标准错误输出提示。"""
    assert main([str(ORIGIN)]) == 2
    assert "需要 3 个参数" in capsys.readouterr().err


def test_main_reports_missing_file(tmp_path, capsys):
    """文件不存在时返回退出码 3。"""
    exit_code = main([str(tmp_path / "无此文件.txt"), str(COPY), str(tmp_path / "ans.txt")])
    assert exit_code == 3
    assert "文件不存在" in capsys.readouterr().err


def test_main_reports_encoding_error(tmp_path, capsys):
    """编码无法识别时返回退出码 4。"""
    broken = tmp_path / "broken.bin"
    broken.write_bytes(b"\x80\x81\x8f\x90\x9f\xa0\xff\xfe\xfd\x80\x81\x80")
    exit_code = main([str(broken), str(COPY), str(tmp_path / "ans.txt")])
    assert exit_code == 4
    assert "编码" in capsys.readouterr().err


def test_main_prints_usage_for_help_flag(capsys):
    """-h 打印用法说明并正常退出。"""
    assert main(["-h"]) == 0
    assert USAGE in capsys.readouterr().out


def test_main_warns_on_empty_copy(tmp_path, capsys):
    """抄袭版为空时仍然正常退出，只给出警告。"""
    answer = tmp_path / "ans.txt"
    exit_code = main([str(ORIGIN), str(DATA_DIR / "orig_empty.txt"), str(answer)])
    assert exit_code == 0
    assert answer.read_text(encoding="utf-8").strip() == "0.00"
    assert "[警告]" in capsys.readouterr().err


def test_command_line_end_to_end(tmp_path):
    """按作业要求的方式真实调用：python main.py 原文 抄袭版 答案。"""
    answer = tmp_path / "ans.txt"
    completed = subprocess.run(
        [sys.executable, "main.py", str(ORIGIN), str(COPY), str(answer)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0
    assert answer.read_text(encoding="utf-8").strip() == "0.93"
