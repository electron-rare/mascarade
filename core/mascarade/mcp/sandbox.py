"""FreeCAD script sandboxing — AST-based validation for safe execution."""

from __future__ import annotations

import ast

_FREECAD_BLOCKED_SNIPPETS = (
    "import os",
    "from os",
    "import subprocess",
    "from subprocess",
    "import socket",
    "from socket",
    "__import__",
    "eval(",
    "exec(",
    "open(",
)
_FREECAD_ALLOWED_IMPORT_ROOTS = {
    "FreeCAD",
    "App",
    "Part",
    "math",
    "json",
}
_FREECAD_BLOCKED_MODULE_NAMES = {
    "os",
    "subprocess",
    "socket",
    "pathlib",
    "sys",
    "shutil",
    "builtins",
}
_FREECAD_BLOCKED_CALLS = {
    "__import__",
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "help",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
}


def _validate_freecad_script(script: str) -> None:
    if len(script) > 20_000:
        raise ValueError("FreeCAD script too large (max 20,000 chars)")

    lowered = script.lower()
    for snippet in _FREECAD_BLOCKED_SNIPPETS:
        if snippet in lowered:
            raise ValueError(f"FreeCAD script contains blocked pattern: {snippet}")

    try:
        tree = ast.parse(script, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"FreeCAD script syntax error: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _FREECAD_ALLOWED_IMPORT_ROOTS:
                    raise ValueError(f"FreeCAD script blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").strip()
            root = module.split(".", 1)[0] if module else ""
            if node.level != 0 or root not in _FREECAD_ALLOWED_IMPORT_ROOTS:
                raise ValueError(f"FreeCAD script blocked import-from: {module or '<relative>'}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FREECAD_BLOCKED_CALLS:
                raise ValueError(f"FreeCAD script blocked function call: {node.func.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                raise ValueError(f"FreeCAD script blocked dunder attribute: {node.attr}")
            if isinstance(node.value, ast.Name) and node.value.id in _FREECAD_BLOCKED_MODULE_NAMES:
                raise ValueError(
                    f"FreeCAD script blocked module access: {node.value.id}.{node.attr}"
                )
        elif isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load) and (
                node.id in _FREECAD_BLOCKED_MODULE_NAMES or node.id.startswith("__")
            ):
                raise ValueError(f"FreeCAD script blocked name usage: {node.id}")
