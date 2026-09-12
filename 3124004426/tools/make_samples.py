"""生成测试用的样例数据。

以 ``data/orig.txt`` 为原文，派生出一组抄袭版论文文件，覆盖需求中提到的
"增、删、改" 三种抄袭方式，以及空文件、编码不同、中英混排等边界情况。

运行方式（在项目根目录下）::

    python tools/make_samples.py
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
ORIGIN_FILE = DATA_DIR / "orig.txt"

#: 与原文完全无关的一篇短文，用于验证"无抄袭"场景。
UNRELATED_TEXT = (
    "清晨的雾气还没有散去，渔船的桨声就从码头那边传了过来。"
    "老张把网具搬上甲板，顺手检查了发动机的油路，然后点燃一支烟，"
    "安静地等着潮水把船推向湾口。今天的风不大，海面像一块灰色的绸缎。"
    "他想起二十年前第一次出海时，父亲也是站在这个位置，一句话都没有说。\n"
)

#: 英文抄袭版：用于验证英文按词切分的效果。
ENGLISH_COPY = (
    "Plagiarism detection is a common way for universities to check the "
    "originality of a thesis. The basic idea is to split the submitted paper "
    "and the reference database into small text units, then count how many of "
    "them can be found in the database, and finally divide the repeated words "
    "by the total words of the submitted paper.\n"
)


def _read_paragraphs() -> list[str]:
    """读取原文并按空行切成段落。"""
    text = ORIGIN_FILE.read_text(encoding="utf-8")
    return [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]


def _write(name: str, text: str, encoding: str = "utf-8") -> Path:
    """把样例写入 ``data`` 目录。"""
    path = DATA_DIR / name
    path.write_text(text, encoding=encoding)
    return path


def build_origin() -> None:
    """生成原文：首段末尾追加一句话，作为"完全复制"以外的对照组。"""
    paragraphs = _read_paragraphs()
    _write("orig_same.txt", "\n\n".join(paragraphs) + "\n")


def build_added() -> None:
    """增：在原文中间插入一个新段落（扩写型抄袭）。"""
    paragraphs = _read_paragraphs()
    inserted = (
        "此外，查重结果并不是判定学术不端的唯一依据。合理的引用、"
        "公式推导与实验描述都可能造成较高的重复率，评审时需要人工复核。"
    )
    paragraphs.insert(3, inserted)
    _write("orig_add.txt", "\n\n".join(paragraphs) + "\n")


def build_deleted() -> None:
    """删：去掉原文的若干段落（缩写型抄袭）。"""
    paragraphs = _read_paragraphs()
    kept = [paragraphs[0], paragraphs[1], paragraphs[4]]
    _write("orig_del.txt", "\n\n".join(kept) + "\n")


def build_modified() -> None:
    """改：逐句做同义替换、全角标点与英文大写混用。"""
    paragraphs = _read_paragraphs()
    modified = []
    for paragraph in paragraphs:
        modified.append(
            paragraph.replace("查重", "重复率检测")
            .replace("论文", "文章")
            .replace("，", "，")
            .replace("。", "．")
        )
    text = "\n\n".join(modified).upper()
    text = text.replace("PYTHON", "Python").replace("UNICODE", "Unicode")
    _write("orig_mod.txt", text + "\n")


def build_reordered() -> None:
    """改：只打乱段落顺序，不修改任何句子。"""
    paragraphs = _read_paragraphs()
    _write("orig_reorder.txt", "\n\n".join(reversed(paragraphs)) + "\n")


def build_edge_cases() -> None:
    """边界样例：无关文章、空文件、纯标点、GBK 编码、中英混排。"""
    paragraphs = _read_paragraphs()
    _write("orig_unrelated.txt", UNRELATED_TEXT)
    _write("orig_empty.txt", "")
    _write("orig_punct.txt", "，。！？；：“”‘’（）【】\n")
    _write("orig_gbk.txt", "\n\n".join(paragraphs) + "\n", encoding="gbk")
    _write("orig_english.txt", ENGLISH_COPY)
    _write("orig_single_char.txt", "晴\n")


def main() -> None:
    """生成全部样例文件。"""
    build_origin()
    build_added()
    build_deleted()
    build_modified()
    build_reordered()
    build_edge_cases()
    print(f"样例文件已生成到 {DATA_DIR}")


if __name__ == "__main__":
    main()
