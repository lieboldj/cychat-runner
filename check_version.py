"""Check that the release version matches RUNNER_VERSION in runner.py."""
import ast
import os
from pathlib import Path
import re


def check_version(value, source):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", value):
        raise ValueError("runner_version must have the form major.minor.patch")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "RUNNER_VERSION"
                for target in node.targets):
            if ast.literal_eval(node.value) == value:
                return
            break
    raise ValueError("runner_version does not match RUNNER_VERSION in runner.py")


if __name__ == "__main__":
    check_version(os.environ["RUNNER_VERSION_INPUT"],
                  Path(__file__).with_name("runner.py").read_text(encoding="utf-8"))
