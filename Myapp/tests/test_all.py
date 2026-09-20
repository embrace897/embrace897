# -*- coding: utf-8 -*-
"""单元测试：数值格式、表达式、去重、生成约束、批改、命令行。

运行方式（在项目根目录下）::

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

from fractions import Fraction
import os
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from myapp.cli import main  # noqa: E402
from myapp.expression import BinOp, Num, parse_expression  # noqa: E402
from myapp.generator import ProblemGenerator, generate_problems  # noqa: E402
from myapp.grader import build_grade_text, grade_lines  # noqa: E402
from myapp.values import build_value_pool, format_value, parse_value  # noqa: E402


def collect_leaves(node):
    if isinstance(node, Num):
        return [node.value]
    return collect_leaves(node.left) + collect_leaves(node.right)


def collect_binops(node):
    if isinstance(node, Num):
        return []
    return [node] + collect_binops(node.left) + collect_binops(node.right)


class ValueFormatTests(unittest.TestCase):
    """需求 6/7 的输入输出格式。"""

    def test_format_value(self):
        self.assertEqual(format_value(Fraction(3)), "3")
        self.assertEqual(format_value(Fraction(3, 5)), "3/5")
        self.assertEqual(format_value(Fraction(19, 8)), "2'3/8")
        self.assertEqual(format_value(Fraction(6, 8)), "3/4")  # 自动约分

    def test_parse_value_accepts_both_apostrophes(self):
        self.assertEqual(parse_value("2'3/8"), Fraction(19, 8))
        self.assertEqual(parse_value("2’3/8"), Fraction(19, 8))
        self.assertEqual(parse_value(" 3 / 5 "), Fraction(3, 5))
        self.assertEqual(parse_value("7"), Fraction(7))

    def test_parse_value_round_trip(self):
        for value in (Fraction(0), Fraction(9), Fraction(1, 6), Fraction(23, 12)):
            self.assertEqual(parse_value(format_value(value)), value)

    def test_parse_value_rejects_bad_input(self):
        for bad in ("3/0", "abc", ""):
            with self.assertRaises(ValueError):
                parse_value(bad)

    def test_value_pool_range(self):
        naturals, fractions = build_value_pool(5)
        self.assertEqual(naturals, [Fraction(i) for i in range(5)])
        self.assertEqual(
            fractions,
            [Fraction(1, 4), Fraction(1, 3), Fraction(1, 2), Fraction(2, 3), Fraction(3, 4)],
        )
        self.assertTrue(all(value < 5 for value in naturals + fractions))


class ExpressionTests(unittest.TestCase):
    """表达式求值、渲染与去重规范形。"""

    def test_evaluate(self):
        self.assertEqual(parse_expression("1/6 + 1/8").value, Fraction(7, 24))
        self.assertEqual(parse_expression("1 + 2 × 3").value, Fraction(7))
        self.assertEqual(parse_expression("(1 + 2) × 3").value, Fraction(9))
        self.assertEqual(parse_expression("1'1/2 + 1/2").value, Fraction(2))
        self.assertEqual(parse_expression("3 ÷ 4").value, Fraction(3, 4))
        self.assertEqual(parse_expression("2 * 3 / 4").value, Fraction(3, 2))

    def test_minimal_parentheses(self):
        self.assertEqual(parse_expression("(1 + 2) + 3").render(), "1 + 2 + 3")
        self.assertEqual(parse_expression("1 + (2 + 3)").render(), "1 + (2 + 3)")
        self.assertEqual(parse_expression("(1 + 2) × 3").render(), "(1 + 2) × 3")
        self.assertEqual(parse_expression("1 + 2 × 3").render(), "1 + 2 × 3")
        self.assertEqual(parse_expression("1 × (2 × 3)").render(), "1 × (2 × 3)")
        self.assertEqual(parse_expression("(1 × 2) × 3").render(), "1 × 2 × 3")

    def test_render_round_trip_keeps_tree(self):
        for text in (
            "1 + 2 + 3",
            "1 + (2 + 3)",
            "(1 + 2) × 3 - 4",
            "1 - 2 ÷ 3",
            "(1 - 2 ÷ 3) × 4",
        ):
            node = parse_expression(text)
            again = parse_expression(node.render())
            self.assertEqual(node.canonical_key(), again.canonical_key())

    def test_duplicate_rules_from_requirement(self):
        """需求 6 中给出的 4 个例子。"""
        self.assertEqual(
            parse_expression("23 + 45").canonical_key(),
            parse_expression("45 + 23").canonical_key(),
        )
        self.assertEqual(
            parse_expression("6 × 8").canonical_key(),
            parse_expression("8 × 6").canonical_key(),
        )
        self.assertEqual(
            parse_expression("3 + (2 + 1)").canonical_key(),
            parse_expression("1 + 2 + 3").canonical_key(),
        )
        self.assertNotEqual(
            parse_expression("1 + 2 + 3").canonical_key(),
            parse_expression("3 + 2 + 1").canonical_key(),
        )

    def test_subtraction_and_division_are_not_commutative(self):
        self.assertNotEqual(
            parse_expression("6 - 8").canonical_key(),
            parse_expression("8 - 6").canonical_key(),
        )
        self.assertNotEqual(
            parse_expression("6 ÷ 8").canonical_key(),
            parse_expression("8 ÷ 6").canonical_key(),
        )


class GeneratorTests(unittest.TestCase):
    """生成器必须同时满足需求 3、4、5、6。"""

    def assert_problem_is_valid(self, problem, r, div_mode="proper"):
        self.assertLessEqual(problem.operator_count(), 3)
        for value in collect_leaves(problem):
            self.assertGreaterEqual(value, 0)
            self.assertLess(value, r)
            if value.denominator != 1:
                self.assertLess(value.numerator, value.denominator)
                self.assertLess(value.denominator, r)
        for node in collect_binops(problem):
            self.assertGreaterEqual(node.value, 0)  # 计算过程不产生负数
            if node.op == "-":
                self.assertGreaterEqual(node.left.value, node.right.value)
            if node.op == "÷":
                self.assertGreater(node.right.value, 0)
                if div_mode == "proper":
                    self.assertGreater(node.value, 0)
                    self.assertLess(node.value, 1)  # 商是真分数

    def test_generated_problems_are_valid_and_unique(self):
        for r in (2, 3, 5, 10, 30):
            problems, _ = generate_problems(300, r, seed=r)
            self.assertEqual(len(problems), 300)
            keys = set()
            for problem in problems:
                self.assert_problem_is_valid(problem, r)
                keys.add(problem.canonical_key())
            self.assertEqual(len(keys), 300)  # 需求 6：没有重复题目

    def test_operator_count_never_exceeds_three(self):
        problems, _ = generate_problems(200, 10, seed=1)
        operator_counts = {p.operator_count() for p in problems}
        self.assertTrue(operator_counts.issubset({1, 2, 3}))

    def test_division_free_when_range_too_small(self):
        """r=2 时取值池只有 0 和 1，无法做出真分数商，应该自动退化为 + - ×。"""
        generator = ProblemGenerator(2, seed=2)
        self.assertEqual(set(generator._usable_operators), {"+", "-", "×"})
        problems, _ = generate_problems(20, 2, seed=2)
        for problem in problems:
            self.assertNotIn("÷", problem.render())

    def test_tiny_range_reports_warning(self):
        """r=1 时只有数值 0，凑不出 1000 道不重复的题目，必须给出提示而不是死循环。"""
        problems, warning = generate_problems(1000, 1, seed=3)
        self.assertIsNotNone(warning)
        self.assertLess(len(problems), 1000)
        self.assertGreater(len(problems), 0)
        self.assertEqual(len({p.canonical_key() for p in problems}), len(problems))
        for problem in problems:
            for value in collect_leaves(problem):
                self.assertEqual(value, Fraction(0))

    def test_div_mode_any_relaxes_constraint(self):
        problems, _ = generate_problems(200, 10, div_mode="any", seed=5)
        self.assertEqual(len(problems), 200)
        for problem in problems:
            for node in collect_binops(problem):
                if node.op == "÷":
                    self.assertGreater(node.right.value, 0)
                    self.assertNotEqual(node.right.value, 0)

    def test_ten_thousand_problems_speed(self):
        """需求 8：支持一万道题目。"""
        start = time.time()
        problems, warning = generate_problems(10000, 100, seed=7)
        elapsed = time.time() - start
        self.assertIsNone(warning)
        self.assertEqual(len(problems), 10000)
        self.assertEqual(len({p.canonical_key() for p in problems}), 10000)
        self.assertLess(elapsed, 60.0, "生成一万道题耗时 %.2f 秒，过慢" % elapsed)


class GraderTests(unittest.TestCase):
    """需求 9：批改并输出 Grade.txt。"""

    def test_grade_lines(self):
        exercises = ["1. 1 + 2 = ", "2. 5 - 8 = ", "3. 3 ÷ 4 = "]
        answers = ["1. 3", "2. 3", "3. 3/4"]
        correct, wrong = grade_lines(exercises, answers)
        self.assertEqual(correct, [1, 3])
        self.assertEqual(wrong, [2])

    def test_grade_text_format(self):
        text = build_grade_text([1, 3, 5, 7, 9], [2, 4, 6, 8, 10])
        self.assertEqual(
            text, "Correct: 5 (1, 3, 5, 7, 9)\nWrong: 5 (2, 4, 6, 8, 10)\n"
        )
        self.assertEqual(build_grade_text([], []) , "Correct: 0 ()\nWrong: 0 ()\n")

    def test_grade_accepts_mixed_number_and_unreducible_answer(self):
        exercises = ["1. 1/2 + 1/2 = ", "2. 2 ÷ 3 = "]
        answers = ["1. 1", "2. 4/6"]  # 4/6 与 2/3 等值，应判为正确
        self.assertEqual(grade_lines(exercises, answers), ([1, 2], []))

    def test_grade_detects_length_mismatch(self):
        with self.assertRaises(ValueError):
            grade_lines(["1. 1 + 1 = "], ["1. 2", "2. 3"])

    def test_grade_wrong_answer_with_unreadable_text(self):
        self.assertEqual(grade_lines(["1. 1 + 1 = "], ["1. 不知道"]), ([], [1]))

    def test_grade_accepts_answers_written_after_equals_sign(self):
        """学生把答案直接写在题目等号后面时也应该能判对。"""
        exercises = ["1. 1 + 2 = ", "2. 3 ÷ 4 = ", "3. 1/2 + 1/2 = "]
        filled = ["1. 1 + 2 = 3", "2. 3 ÷ 4 = 3/4", "3. 1/2 + 1/2 = 1"]
        self.assertEqual(grade_lines(exercises, filled), ([1, 2, 3], []))
        # 同一个"已作答"的文件同时当题目文件和答案文件也成立
        self.assertEqual(grade_lines(filled, filled), ([1, 2, 3], []))


class CliTests(unittest.TestCase):
    """命令行行为（需求 1、2、7、9）。"""

    def test_missing_range_prints_help_and_fails(self):
        # 需求 2：不给 -r 时必须报错并打印帮助信息
        self.assertEqual(main([]), 2)

    def test_generate_then_grade_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(main(["-n", "10", "-r", "10", "-o", temp_dir]), 0)
            exercise_path = os.path.join(temp_dir, "Exercises.txt")
            answer_path = os.path.join(temp_dir, "Answers.txt")
            self.assertTrue(os.path.exists(exercise_path))
            self.assertTrue(os.path.exists(answer_path))

            with open(exercise_path, encoding="utf-8") as handle:
                exercises = [line for line in handle.read().splitlines() if line.strip()]
            with open(answer_path, encoding="utf-8") as handle:
                answers = [line for line in handle.read().splitlines() if line.strip()]
            self.assertEqual(len(exercises), 10)
            self.assertEqual(len(answers), 10)

            # 全部答对 -> Correct: 10 ()
            self.assertEqual(
                main(["-e", exercise_path, "-a", answer_path, "-o", temp_dir]), 0
            )
            grade_path = os.path.join(temp_dir, "Grade.txt")
            with open(grade_path, encoding="utf-8") as handle:
                grade_text = handle.read()
            self.assertIn("Correct: 10", grade_text)
            self.assertIn("Wrong: 0 ()", grade_text)

            # 把第 3 题答案改错 -> Wrong: 1 (3)
            answers[2] = "3. 1/999"
            with open(answer_path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(answers) + "\n")
            self.assertEqual(
                main(["-e", exercise_path, "-a", answer_path, "-o", temp_dir]), 0
            )
            with open(grade_path, encoding="utf-8") as handle:
                grade_text = handle.read()
            self.assertIn("Correct: 9", grade_text)
            self.assertIn("Wrong: 1 (3)", grade_text)

    def test_grade_mode_requires_both_files(self):
        self.assertEqual(main(["-e", "Exercises.txt"]), 2)

    def test_command_line_entry_point(self):
        """用真实的命令行调用，验证 main.py 可以像 Myapp.exe 一样使用。"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [sys.executable, os.path.join(project_root, "main.py"), "-n", "5", "-r", "20"],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            with open(
                os.path.join(temp_dir, "Exercises.txt"), encoding="utf-8"
            ) as handle:
                lines = [line for line in handle.read().splitlines() if line.strip()]
            self.assertEqual(len(lines), 5)
            for index, line in enumerate(lines, start=1):
                self.assertTrue(line.startswith("%d. " % index))
                self.assertTrue(line.rstrip().endswith("="))


if __name__ == "__main__":
    unittest.main(verbosity=2)
