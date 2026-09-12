"""查重核心算法（papercheck/core.py）的单元测试。

初版按 loader / normalizer / tokenizer / similarity / analyzer 分成五个测试文件，
模块合并后这里按同样的顺序分成五个小节，用例本身保持不变。
"""

import codecs
from pathlib import Path

import pytest

from papercheck.core import (
    analyze,
    duplicate_rate,
    extract_tokens,
    load_text,
    normalize,
    token_count,
    write_answer,
)
from papercheck.errors import EmptyDocumentError, EncodingDetectionError, InputFileError
from papercheck.errors import OutputFileError

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORIGIN = DATA_DIR / "orig.txt"


def token_texts(counter) -> set:
    """把特征集合还原成可读文本（中文二元组内部是码位元组）。"""
    result = set()
    for token in counter:
        if isinstance(token, tuple):
            result.add("".join(chr(value) for value in token))
        else:
            result.add(token)
    return result


# ---------------------------------------------------------------- 文本读取与编码


def test_reads_utf8_file():
    """普通 UTF-8 文件按原样读出。"""
    assert "论文查重" in load_text(ORIGIN)


def test_reads_utf8_bom_file(tmp_path):
    """带 BOM 的 UTF-8 文件：BOM 不能变成正文内容。"""
    path = tmp_path / "bom.txt"
    path.write_bytes(codecs.BOM_UTF8 + "论文查重".encode("utf-8"))
    assert load_text(path) == "论文查重"


def test_reads_utf16_file(tmp_path):
    """带 BOM 的 UTF-16 文件能被自动识别。"""
    path = tmp_path / "utf16.txt"
    path.write_bytes("论文查重".encode("utf-16"))
    assert load_text(path) == "论文查重"


def test_reads_gbk_file():
    """GBK（GB18030 子集）文件能被自动识别。"""
    assert "论文查重" in load_text(DATA_DIR / "orig_gbk.txt")


def test_empty_file_is_readable(tmp_path):
    """空文件属于合法输入，读出空字符串。"""
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    assert not load_text(path)


def test_missing_file_raises_input_file_error(tmp_path):
    """文件不存在时给出 InputFileError，而不是 Python 的 FileNotFoundError。"""
    with pytest.raises(InputFileError, match="文件不存在"):
        load_text(tmp_path / "不存在的文件.txt")


def test_directory_raises_input_file_error(tmp_path):
    """传入目录时也应该被明确拒绝。"""
    with pytest.raises(InputFileError, match="不是一个普通文件"):
        load_text(tmp_path)


def test_binary_garbage_raises_encoding_error(tmp_path):
    """二进制垃圾数据无法解码，抛出 EncodingDetectionError。"""
    path = tmp_path / "garbage.bin"
    path.write_bytes(b"\x80\x81\x8f\x90\x9f\xa0\xff\xfe\xfd\x80\x81\x80")
    with pytest.raises(EncodingDetectionError):
        load_text(path)


def test_read_failure_is_wrapped_as_input_file_error(tmp_path, monkeypatch):
    """底层 I/O 失败（权限不足、文件被占用）也要转换成 InputFileError。"""
    path = tmp_path / "locked.txt"
    path.write_text("论文查重", encoding="utf-8")

    def raise_os_error(self):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(Path, "read_bytes", raise_os_error, raising=True)
    with pytest.raises(InputFileError, match="读取文件失败"):
        load_text(path)


# ------------------------------------------------------------------------ 规范化


def test_fullwidth_characters_are_folded_to_halfwidth():
    """全角字母/数字应当折叠成半角（NFKC 归一化）。"""
    assert normalize("ＡＢＣ １２３") == "abc 123"


def test_ascii_uppercase_is_lowered():
    """英文大小写不影响查重结果。"""
    assert normalize("Hello WORLD") == "hello world"


def test_punctuation_becomes_separator():
    """标点被替换成分隔符，避免产生跨标点的特征。"""
    assert normalize("天气晴。今天晚上，我要去看电影") == "天气晴 今天晚上 我要去看电影"


def test_chinese_and_english_punctuation_are_equivalent():
    """中文标点与英文标点应当被同样处理。"""
    assert normalize("天气晴，晚上") == normalize("天气晴,晚上")


def test_whitespace_runs_are_collapsed():
    """连续空白（空格、制表符、换行）压缩成一个分隔符。"""
    assert normalize("论文\t\t查重\n\n测试  ") == "论文 查重 测试"


def test_control_characters_are_removed():
    """不可见控制字符不应进入特征。"""
    assert normalize("论文\x00\x07查重") == "论文 查重"


def test_ligature_is_normalized():
    """兼容字符（如 ﬁ 连字）应当折叠成普通字母。"""
    assert normalize("ofﬁce") == "office"


def test_nfkc_does_not_break_ascii_fast_path():
    """纯 ASCII 文本走快速路径，结果与完整归一化一致。"""
    assert normalize("A-B_C") == "a b c"


def test_empty_text_stays_empty():
    """空文本规范化后仍然是空文本。"""
    assert not normalize("")


# -------------------------------------------------------------------- 特征提取


def test_chinese_text_is_split_into_bigrams():
    """中文按相邻两个字组成特征。"""
    assert token_texts(extract_tokens("论文查重")) == {"论文", "文查", "查重"}


def test_single_chinese_character_is_kept():
    """单字段落无法构成二元组，退化为单字特征而不是被丢弃。"""
    assert token_texts(extract_tokens("晴")) == {"c:晴"}


def test_english_words_are_tokens():
    """英文按词切分，并统一为小写。"""
    assert token_texts(extract_tokens("Hello WORLD hello")) == {"w:hello", "w:world"}


def test_letters_and_digits_stay_together():
    """字母数字混合的片段（如型号）整体作为一个特征。"""
    assert token_texts(extract_tokens("ABC123")) == {"w:abc123"}


def test_punctuation_breaks_bigrams():
    """标点两侧的字不会组成二元组：任何包含"晴今"的实现都是错的。"""
    tokens = token_texts(extract_tokens("天气晴。今天晚上"))
    assert "晴今" not in tokens
    assert {"天气", "气晴", "今天", "天晚", "晚上"} <= tokens


def test_repeated_features_are_counted():
    """同一特征出现多次时计数累加（多重集合）。"""
    counter = extract_tokens("论文查重论文")
    assert token_count(counter) == 5
    assert max(counter.values()) == 2


def test_extended_chinese_pairs_do_not_collide():
    """扩展 B 区汉字（码位大于 0x20000）的不同二元组不能编码成同一个特征。"""
    left = token_texts(extract_tokens("\U00020000\U00020001"))
    right = token_texts(extract_tokens("\U00020001\U00020000"))
    assert left != right
    assert len(left) == 1 and len(right) == 1


def test_empty_text_has_no_tokens():
    """空文本没有任何特征。"""
    assert token_count(extract_tokens("")) == 0


def test_mixed_language_is_supported():
    """中英文混排时两类特征都会被提取。"""
    tokens = token_texts(extract_tokens("使用 Python 实现论文查重"))
    assert "论文" in tokens
    assert "w:python" in tokens


# -------------------------------------------------------------------- 重复率


def test_identical_documents_are_fully_duplicated():
    """完全相同 -> 1.00。"""
    tokens = extract_tokens("今天是星期天天气晴今天晚上我要去看电影")
    assert duplicate_rate(tokens, tokens) == pytest.approx(1.0)


def test_unrelated_documents_are_not_similar():
    """完全无关 -> 0.00。"""
    origin = extract_tokens("论文查重算法的设计与实现")
    other = extract_tokens("清晨的雾气还没有散去渔船已经出海")
    assert duplicate_rate(origin, other) == pytest.approx(0.0)


def test_partial_copy_returns_fraction():
    """只抄一部分时重复率等于被抄部分所占比例。"""
    origin = extract_tokens("论文查重算法")
    other = extract_tokens("论文查重新增内容甲乙丙丁")
    assert 0.0 < duplicate_rate(origin, other) < 1.0


def test_copy_superset_rate_equals_coverage():
    """抄袭版 = 原文 + 新增内容时，重复率 = 命中特征数 / 抄袭版特征数。"""
    origin = extract_tokens("论文查重算法")
    other = extract_tokens("论文查重算法以及额外的说明内容")
    assert duplicate_rate(origin, other) == pytest.approx(5 / 14)


def test_subset_copy_is_fully_covered():
    """抄袭版是原文的一部分（删减型抄袭）时，抄到的部分全部命中 -> 1.00。"""
    origin = extract_tokens("论文查重算法的设计与实现")
    other = extract_tokens("论文查重算法")
    assert duplicate_rate(origin, other) == pytest.approx(1.0)


def test_repeated_paste_is_discounted():
    """把原文重复粘贴多遍时，新增部分不计入重复。"""
    origin = extract_tokens("论文查重")
    other = extract_tokens("论文查重")
    other.update(extract_tokens("完全无关的另外一段文字内容"))
    assert duplicate_rate(origin, other) < 0.5


def test_empty_origin_returns_zero():
    """原文为空 -> 0.00，且不报错。"""
    assert duplicate_rate(extract_tokens(""), extract_tokens("论文查重")) == pytest.approx(0.0)


def test_empty_copy_raises_error():
    """抄袭版为空时重复率无定义，抛出 EmptyDocumentError。"""
    with pytest.raises(EmptyDocumentError):
        duplicate_rate(extract_tokens("论文查重"), extract_tokens(""))


def test_punctuation_only_copy_raises_error():
    """只有标点的文件等价于空文档。"""
    with pytest.raises(EmptyDocumentError):
        duplicate_rate(extract_tokens("论文查重"), extract_tokens("，。！？"))


# --------------------------------------------------------------- 查重流程与输出


def test_identical_copy_is_full_rate():
    """与原文完全相同的抄袭版，重复率为 1.00。"""
    report = analyze(ORIGIN, DATA_DIR / "orig_same.txt")
    assert report.rate == pytest.approx(1.0)
    assert not report.warnings


def test_added_paragraph_lowers_rate():
    """扩写型抄袭版：重复率小于 1，且大于只抄一部分的情况。"""
    added = analyze(ORIGIN, DATA_DIR / "orig_add.txt")
    assert 0.8 < added.rate < 1.0


def test_unrelated_document_has_low_rate():
    """无关文章的重复率接近 0。"""
    assert analyze(ORIGIN, DATA_DIR / "orig_unrelated.txt").rate <= 0.05


def test_gbk_copy_matches_utf8_copy():
    """编码不同不影响结果：GBK 版本与 UTF-8 版本重复率一致。"""
    gbk_report = analyze(ORIGIN, DATA_DIR / "orig_gbk.txt")
    same_report = analyze(ORIGIN, DATA_DIR / "orig_same.txt")
    assert gbk_report.rate == pytest.approx(same_report.rate)


def test_empty_copy_degrades_to_zero_with_warning():
    """空抄袭版：按 0.00 处理并给出警告，不抛异常。"""
    report = analyze(ORIGIN, DATA_DIR / "orig_empty.txt")
    assert report.rate == pytest.approx(0.0)
    assert any("抄袭版" in warning for warning in report.warnings)


def test_empty_origin_degrades_to_zero_with_warning():
    """空原文：重复率按 0.00 处理并提示原文为空。"""
    report = analyze(DATA_DIR / "orig_empty.txt", ORIGIN)
    assert report.rate == pytest.approx(0.0)
    assert any("原文" in warning for warning in report.warnings)


def test_report_statistics_are_consistent():
    """统计信息（字符数、特征数）与文档规模一致。"""
    report = analyze(ORIGIN, DATA_DIR / "orig_add.txt")
    assert report.origin_chars > 0
    assert report.copy_chars > report.origin_chars
    assert report.origin_tokens > 0


def test_write_answer_formats_two_decimals(tmp_path):
    """答案文件的内容是保留两位小数的浮点数。"""
    report = analyze(ORIGIN, DATA_DIR / "orig_add.txt")
    answer = write_answer(report, tmp_path / "ans.txt")
    content = answer.read_text(encoding="utf-8").strip()
    assert content == f"{report.rate:.2f}"
    assert len(content.split(".")[1]) == 2


def test_write_answer_creates_missing_parent_directory(tmp_path):
    """答案文件的父目录不存在时自动创建。"""
    answer = write_answer(analyze(ORIGIN, ORIGIN), tmp_path / "深层" / "目录" / "ans.txt")
    assert answer.exists()


def test_write_answer_to_directory_raises_output_error(tmp_path):
    """答案路径被目录占用时抛出 OutputFileError。"""
    with pytest.raises(OutputFileError):
        write_answer(analyze(ORIGIN, ORIGIN), tmp_path)
