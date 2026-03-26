#!/usr/bin/env python3
"""Minimal HumanEval benchmark against an Ollama model endpoint.

Usage:
    python scripts/eval/humaneval_eval.py --url http://localhost:11434 --model mascarade-coder --n 30
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

# HumanEval problems subset (representative 30 problems)
HUMANEVAL_PROBLEMS = [
    {
        "task_id": "HumanEval/0",
        "prompt": 'from typing import List\n\n\ndef has_close_elements(numbers: List[float], threshold: float) -> bool:\n    """ Check if in given list of numbers, are any two numbers closer to each other than\n    given threshold.\n    >>> has_close_elements([1.0, 2.0, 3.0], 0.5)\n    False\n    >>> has_close_elements([1.0, 2.8, 3.0, 4.0, 5.0, 2.0], 0.3)\n    True\n    """\n',
        "test": "def check(candidate):\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.3) == True\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) == False\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.95) == True\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0], 0.8) == False\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0, 2.0], 0.1) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 1.0) == True\n    assert candidate([1.1, 2.2, 3.1, 4.1, 5.1], 0.5) == False\ncheck(has_close_elements)",
        "entry_point": "has_close_elements",
    },
    {
        "task_id": "HumanEval/1",
        "prompt": "from typing import List\n\n\ndef separate_paren_groups(paren_string: str) -> List[str]:\n    \"\"\" Input to this function is a string containing multiple groups of nested parentheses. Your goal is to\n    separate those group into separate strings and return the list of those.\n    Separate groups are balanced (each open brace is properly closed) and not nested within each other\n    Ignore any spaces in the input string.\n    >>> separate_paren_groups('( ) (( )) (( )( ))')\n    ['()', '(())', '(()())']\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate('(()()) ((())) () ((())()())') == ['(()())', '((()))', '()', '((())()())']\n    assert candidate('() (()) ((())) (((())))') == ['()', '(())', '((()))', '(((())))']\n    assert candidate('(()(())((())))') == ['(()(())((())))']\n    assert candidate('( ) (( )) (( )( ))') == ['()', '(())', '(()())']\ncheck(separate_paren_groups)",
        "entry_point": "separate_paren_groups",
    },
    {
        "task_id": "HumanEval/2",
        "prompt": '\n\ndef truncate_number(number: float) -> float:\n    """ Given a positive floating point number, it can be decomposed into\n    and integer part (largest integer smaller than given number) and decimals\n    (leftover part always smaller than 1).\n\n    Return the decimal part of the number.\n    >>> truncate_number(3.5)\n    0.5\n    """\n',
        "test": "def check(candidate):\n    assert candidate(3.5) == 0.5\n    assert abs(candidate(1.33) - 0.33) < 1e-6\n    assert abs(candidate(123.456) - 0.456) < 1e-6\ncheck(truncate_number)",
        "entry_point": "truncate_number",
    },
    {
        "task_id": "HumanEval/4",
        "prompt": 'from typing import List\n\n\ndef mean_absolute_deviation(numbers: List[float]) -> float:\n    """ For a given list of input numbers, calculate Mean Absolute Deviation\n    around the mean of this dataset.\n    Mean Absolute Deviation is the average absolute difference between each\n    element and a centerpoint (mean in this case):\n    MAD = average | x - x_mean |\n    >>> mean_absolute_deviation([1.0, 2.0, 3.0, 4.0])\n    1.0\n    """\n',
        "test": "def check(candidate):\n    assert abs(candidate([1.0, 2.0, 3.0]) - 2.0/3.0) < 1e-6\n    assert abs(candidate([1.0, 2.0, 3.0, 4.0]) - 1.0) < 1e-6\n    assert abs(candidate([1.0, 2.0, 3.0, 4.0, 5.0]) - 1.2) < 1e-6\ncheck(mean_absolute_deviation)",
        "entry_point": "mean_absolute_deviation",
    },
    {
        "task_id": "HumanEval/5",
        "prompt": 'from typing import List\n\n\ndef intersperse(numbers: List[int], delimeter: int) -> List[int]:\n    """ Insert a number \'delimeter\' between every two consecutive elements of input list `numbers\'\n    >>> intersperse([], 4)\n    []\n    >>> intersperse([1, 2, 3], 4)\n    [1, 4, 2, 4, 3]\n    """\n',
        "test": "def check(candidate):\n    assert candidate([], 7) == []\n    assert candidate([5, 6, 3, 2], 8) == [5, 8, 6, 8, 3, 8, 2]\n    assert candidate([2, 2, 2], 2) == [2, 2, 2, 2, 2]\ncheck(intersperse)",
        "entry_point": "intersperse",
    },
    {
        "task_id": "HumanEval/6",
        "prompt": 'from typing import List\n\n\ndef parse_nested_parens(paren_string: str) -> List[int]:\n    """ Input to this function is a string represented multiple groups of nested parentheses separated by spaces.\n    For each of the group, output the deepest level of nesting of parentheses.\n    E.g. (()()) has maximum two levels of nesting while ((())) has three.\n\n    >>> parse_nested_parens(\'(()()) ((())) () ((())()())\')\n    [2, 3, 1, 3]\n    """\n',
        "test": "def check(candidate):\n    assert candidate('(()()) ((())) () ((())()())') == [2, 3, 1, 3]\n    assert candidate('() (()) ((())) (((())))') == [1, 2, 3, 4]\n    assert candidate('(()(())((())))') == [4]\ncheck(parse_nested_parens)",
        "entry_point": "parse_nested_parens",
    },
    {
        "task_id": "HumanEval/7",
        "prompt": "from typing import List\n\n\ndef filter_by_substring(strings: List[str], substring: str) -> List[str]:\n    \"\"\" Filter an input list of strings only for ones that contain given substring\n    >>> filter_by_substring([], 'a')\n    []\n    >>> filter_by_substring(['abc', 'bacd', 'cde', 'array'], 'a')\n    ['abc', 'bacd', 'array']\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate([], 'john') == []\n    assert candidate(['xxx', 'asd', 'xxy', 'john doe', 'xxxuj', 'jjohn'], 'john') == ['john doe', 'jjohn']\n    assert candidate(['xxx', 'asd', 'aaber'], 'a') == ['asd', 'aaber']\ncheck(filter_by_substring)",
        "entry_point": "filter_by_substring",
    },
    {
        "task_id": "HumanEval/8",
        "prompt": 'from typing import List, Tuple\n\n\ndef sum_product(numbers: List[int]) -> Tuple[int, int]:\n    """ For a given list of integers, return a tuple consisting of a sum and a product of all the integers in a list.\n    Empty sum should be equal to 0 and empty product should be equal to 1.\n    >>> sum_product([])\n    (0, 1)\n    >>> sum_product([1, 2, 3, 4])\n    (10, 24)\n    """\n',
        "test": "def check(candidate):\n    assert candidate([]) == (0, 1)\n    assert candidate([1, 1, 1]) == (3, 1)\n    assert candidate([100, 0]) == (100, 0)\n    assert candidate([3, 5, 7]) == (15, 105)\n    assert candidate([10]) == (10, 10)\ncheck(sum_product)",
        "entry_point": "sum_product",
    },
    {
        "task_id": "HumanEval/9",
        "prompt": 'from typing import List, Tuple\n\n\ndef rolling_max(numbers: List[int]) -> List[int]:\n    """ From a given list of integers, generate a list of rolling maximum element found until given moment\n    in the sequence.\n    >>> rolling_max([1, 2, 3, 2, 3, 4, 2])\n    [1, 2, 3, 3, 3, 4, 4]\n    """\n',
        "test": "def check(candidate):\n    assert candidate([]) == []\n    assert candidate([1, 2, 3, 4]) == [1, 2, 3, 4]\n    assert candidate([4, 3, 2, 1]) == [4, 4, 4, 4]\n    assert candidate([3, 2, 3, 100, 3]) == [3, 3, 3, 100, 100]\ncheck(rolling_max)",
        "entry_point": "rolling_max",
    },
    {
        "task_id": "HumanEval/11",
        "prompt": "from typing import List\n\n\ndef string_xor(a: str, b: str) -> str:\n    \"\"\" Input are two strings a and b consisting only of 1s and 0s.\n    Perform binary XOR on these inputs and return result also as a string.\n    >>> string_xor('010', '110')\n    '100'\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate('111000', '101010') == '010010'\n    assert candidate('1', '1') == '0'\n    assert candidate('0101', '0000') == '0101'\ncheck(string_xor)",
        "entry_point": "string_xor",
    },
    {
        "task_id": "HumanEval/12",
        "prompt": "from typing import List, Optional\n\n\ndef longest(strings: List[str]) -> Optional[str]:\n    \"\"\" Out of list of strings, return the longest one. Return the first one in case of multiple\n    strings of the same length. Return None in case the input list is empty.\n    >>> longest([])\n\n    >>> longest(['a', 'b', 'c'])\n    'a'\n    >>> longest(['a', 'bb', 'ccc'])\n    'ccc'\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate([]) is None\n    assert candidate(['x', 'y', 'z']) == 'x'\n    assert candidate(['x', 'yyy', 'zzzz', 'www', 'kkkk', 'abc']) == 'zzzz'\ncheck(longest)",
        "entry_point": "longest",
    },
    {
        "task_id": "HumanEval/13",
        "prompt": '\n\ndef greatest_common_divisor(a: int, b: int) -> int:\n    """ Return a greatest common divisor of two integers a and b\n    >>> greatest_common_divisor(3, 5)\n    1\n    >>> greatest_common_divisor(25, 15)\n    5\n    """\n',
        "test": "def check(candidate):\n    assert candidate(3, 7) == 1\n    assert candidate(10, 15) == 5\n    assert candidate(49, 14) == 7\n    assert candidate(144, 60) == 12\ncheck(greatest_common_divisor)",
        "entry_point": "greatest_common_divisor",
    },
    {
        "task_id": "HumanEval/14",
        "prompt": "from typing import List\n\n\ndef all_prefixes(string: str) -> List[str]:\n    \"\"\" Return list of all prefixes from shortest to longest of the input string\n    >>> all_prefixes('abc')\n    ['a', 'ab', 'abc']\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate('') == []\n    assert candidate('asdfgh') == ['a', 'as', 'asd', 'asdf', 'asdg', 'asdfg', 'asdfgh'] or candidate('asdfgh') == ['a', 'as', 'asd', 'asdf', 'asdfg', 'asdfgh']\n    assert candidate('WWW') == ['W', 'WW', 'WWW']\ncheck(all_prefixes)",
        "entry_point": "all_prefixes",
    },
    {
        "task_id": "HumanEval/15",
        "prompt": '\n\ndef string_sequence(n: int) -> str:\n    """ Return a string containing space-delimited numbers starting from 0 upto n inclusive.\n    >>> string_sequence(0)\n    \'0\'\n    >>> string_sequence(5)\n    \'0 1 2 3 4 5\'\n    """\n',
        "test": "def check(candidate):\n    assert candidate(0) == '0'\n    assert candidate(3) == '0 1 2 3'\n    assert candidate(10) == '0 1 2 3 4 5 6 7 8 9 10'\ncheck(string_sequence)",
        "entry_point": "string_sequence",
    },
    {
        "task_id": "HumanEval/17",
        "prompt": "from typing import List\n\n\ndef parse_music(music_string: str) -> List[int]:\n    \"\"\" Input to this function is a string representing musical notes in a special ASCII format.\n    Your task is to parse this string and return list of integers corresponding to how many beats does each\n    not last.\n\n    Here is a legend:\n    'o' - whole note, lasts four beats\n    'o|' - half note, lasts two beats\n    '.|' - quarter note, lasts one beat\n\n    >>> parse_music('o o| .| o| o| .| .| .| .| o o')\n    [4, 2, 1, 2, 2, 1, 1, 1, 1, 4, 4]\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate('') == []\n    assert candidate('o o o o') == [4, 4, 4, 4]\n    assert candidate('.| .| .| .|') == [1, 1, 1, 1]\n    assert candidate('o| o| .| .| o o o o') == [2, 2, 1, 1, 4, 4, 4, 4]\n    assert candidate('o| .| o| .| o o| o o|') == [2, 1, 2, 1, 4, 2, 4, 2]\ncheck(parse_music)",
        "entry_point": "parse_music",
    },
    {
        "task_id": "HumanEval/18",
        "prompt": "\n\ndef how_many_times(string: str, substring: str) -> int:\n    \"\"\" Find how many times a given substring can be found in the original string. Count overlaping cases.\n    >>> how_many_times('', 'a')\n    0\n    >>> how_many_times('aaa', 'a')\n    3\n    >>> how_many_times('aaaa', 'aa')\n    3\n    \"\"\"\n",
        "test": "def check(candidate):\n    assert candidate('', 'x') == 0\n    assert candidate('xyxyxyx', 'x') == 4\n    assert candidate('cacacacac', 'cac') == 4\ncheck(how_many_times)",
        "entry_point": "how_many_times",
    },
    {
        "task_id": "HumanEval/20",
        "prompt": 'from typing import List, Tuple\n\n\ndef find_closest_elements(numbers: List[float]) -> Tuple[float, float]:\n    """ From a supplied list of numbers (of length at least two) select and return two that are the closest to each\n    other and return them in order (smaller number, larger number).\n    >>> find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.2])\n    (2.0, 2.2)\n    >>> find_closest_elements([1.0, 2.0, 3.0, 4.0, 5.0, 2.0])\n    (2.0, 2.0)\n    """\n',
        "test": "def check(candidate):\n    assert candidate([1.0, 2.0, 3.9, 4.0, 5.0, 2.2]) == (3.9, 4.0)\n    assert candidate([1.0, 2.0, 5.9, 4.0, 5.0]) == (5.0, 5.9)\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0, 2.2]) == (2.0, 2.2)\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0, 2.0]) == (2.0, 2.0)\ncheck(find_closest_elements)",
        "entry_point": "find_closest_elements",
    },
    {
        "task_id": "HumanEval/21",
        "prompt": 'from typing import List\n\n\ndef rescale_to_unit(numbers: List[float]) -> List[float]:\n    """ Given list of numbers (of at least two elements), apply a linear transform to that list,\n    such that the smallest number will become 0 and the largest will become 1\n    >>> rescale_to_unit([1.0, 2.0, 3.0, 4.0, 5.0])\n    [0.0, 0.25, 0.5, 0.75, 1.0]\n    """\n',
        "test": "def check(candidate):\n    assert candidate([2.0, 49.9]) == [0.0, 1.0]\n    assert candidate([100.0, 49.9]) == [1.0, 0.0]\n    assert candidate([1.0, 2.0, 3.0, 4.0, 5.0]) == [0.0, 0.25, 0.5, 0.75, 1.0]\n    assert candidate([2.0, 1.0, 5.0, 3.0, 4.0]) == [0.25, 0.0, 1.0, 0.5, 0.75]\ncheck(rescale_to_unit)",
        "entry_point": "rescale_to_unit",
    },
    {
        "task_id": "HumanEval/22",
        "prompt": 'from typing import List, Any\n\n\ndef filter_integers(values: List[Any]) -> List[int]:\n    """ Filter given list of any python values only for integers\n    >>> filter_integers([\'a\', 3.14, 5])\n    [5]\n    >>> filter_integers([1, 2, 3, \'abc\', {}, []])\n    [1, 2, 3]\n    """\n',
        "test": "def check(candidate):\n    assert candidate([]) == []\n    assert candidate([4, {}, [], 23.2, 9, 'adasd']) == [4, 9]\n    assert candidate([3, 'c', 3, 3, 'a', 'b']) == [3, 3, 3]\ncheck(filter_integers)",
        "entry_point": "filter_integers",
    },
    {
        "task_id": "HumanEval/23",
        "prompt": '\n\ndef strlen(string: str) -> int:\n    """ Return length of given string\n    >>> strlen(\'\')\n    0\n    >>> strlen(\'abc\')\n    3\n    """\n',
        "test": "def check(candidate):\n    assert candidate('') == 0\n    assert candidate('x') == 1\n    assert candidate('asdasnakj') == 9\ncheck(strlen)",
        "entry_point": "strlen",
    },
]


def query_ollama(url: str, model: str, prompt: str, max_tokens: int = 512) -> tuple[str, float]:
    """Query Ollama using chat template and return (response, duration_seconds)."""
    chat_prompt = (
        "<|im_start|>system\n"
        "You are a code completion assistant. Complete the following Python function. "
        "Output ONLY the function body code, no explanation, no markdown.\n"
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"{prompt}\n"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
    data = json.dumps(
        {
            "model": model,
            "prompt": chat_prompt,
            "stream": False,
            "raw": True,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.0,
                "stop": ["<|im_end|>"],
            },
        }
    ).encode()
    req = urllib.request.Request(
        f"{url}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read())
    elapsed = time.time() - t0
    return result.get("response", ""), elapsed


def extract_function(prompt: str, completion: str, entry_point: str) -> str:
    """Build the full function from prompt + completion."""
    import re

    code = completion.strip()
    # Strip markdown code blocks if present
    code = re.sub(r"^```(?:python)?\s*\n?", "", code)
    code = re.sub(r"\n?```\s*$", "", code)
    # Stop at common end markers
    for stop in ["\nclass ", "\ndef ", "\n#", "\nif __name__", "\nprint("]:
        idx = code.find(stop)
        if idx > 0:
            code = code[:idx]
    # Indent if not already indented (model may return bare code)
    lines = code.split("\n")
    if lines and not lines[0].startswith("    ") and not lines[0].startswith("\t"):
        code = "\n".join("    " + line for line in lines)
    return prompt + code


def run_test(full_code: str, test_code: str, timeout: int = 10) -> bool:
    """Execute the function + test in a subprocess, return pass/fail."""
    program = full_code + "\n" + test_code
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(program)
        f.flush()
        try:
            result = subprocess.run(
                [sys.executable, f.name],
                capture_output=True,
                timeout=timeout,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        finally:
            Path(f.name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:11434")
    parser.add_argument("--model", default="mascarade-coder")
    parser.add_argument("--n", type=int, default=20, help="Number of problems to evaluate")
    args = parser.parse_args()

    problems = HUMANEVAL_PROBLEMS[: args.n]
    passed = 0
    total = 0
    times = []

    print(f"=== HumanEval Benchmark: {args.model} @ {args.url} ===")
    print(f"Problems: {len(problems)}")
    print()

    for prob in problems:
        task_id = prob["task_id"]
        total += 1
        try:
            completion, elapsed = query_ollama(args.url, args.model, prob["prompt"])
            times.append(elapsed)
            full_code = extract_function(prob["prompt"], completion, prob["entry_point"])
            ok = run_test(full_code, prob["test"])
            status = "PASS" if ok else "FAIL"
            if ok:
                passed += 1
            print(f"  {task_id}: {status} ({elapsed:.1f}s)")
        except Exception as e:
            print(f"  {task_id}: ERROR ({e})")

    print()
    score = passed / total * 100 if total else 0
    avg_time = sum(times) / len(times) if times else 0
    print("=== Results ===")
    print(f"  pass@1: {passed}/{total} = {score:.1f}%")
    print(f"  Avg time/problem: {avg_time:.1f}s")
    print("  Baseline Qwen2.5-Coder-1.5B-Instruct: 61.6%")
    print(f"  Delta: {score - 61.6:+.1f}pp")


if __name__ == "__main__":
    main()
