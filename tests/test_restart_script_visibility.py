import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main_tree() -> ast.Module:
    return ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))


def function_node(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


def uses_hidden_restart_flags(node: ast.FunctionDef) -> bool:
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "Popen":
            continue
        if not isinstance(call.func.value, ast.Name) or call.func.value.id != "subprocess":
            continue
        for keyword in call.keywords:
            if keyword.arg == "creationflags":
                value = keyword.value
                return isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "hidden_windows_restart_flags"
    return False


def test_windows_restart_scripts_are_launched_without_console_window():
    tree = main_tree()
    flags = function_node(tree, "hidden_windows_restart_flags")
    flag_names = {
        node.args[1].value
        for node in ast.walk(flags)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
    }

    assert "CREATE_NO_WINDOW" in flag_names
    assert uses_hidden_restart_flags(function_node(tree, "schedule_launcher_restart"))
    assert uses_hidden_restart_flags(function_node(tree, "schedule_self_restart"))
