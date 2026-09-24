#!/usr/bin/env python3
"""Run Python code with JSON results or streaming output."""

import argparse
import contextlib
import io
import json
import math
import os
import pathlib
import runpy
import sys
import threading
import time
import traceback


RUNNER_VERSION = "2.1.0"


def _app_tmp_dir() -> pathlib.Path:
    tmp = pathlib.Path.home() / ".cytoscape-ai" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="script-runner",
        description="Run a Python script and return a JSON result.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--licenses", action="store_true", help="Print bundled licenses and source availability.")
    p.add_argument("--version", action="store_true", help="Print runner and Python versions.")

    p.add_argument("--script", metavar="PATH", required=True, help="Python script to run.")
    p.epilog = "Pass script arguments as separate values after --; no shell splitting is applied."
    p.add_argument(
        "--timeout", metavar="SEC", type=float, default=30.0,
        help="Kill the process after this many seconds (default: 30).",
    )
    p.add_argument(
        "--workdir", metavar="PATH", default=None,
        help=(
            "Working directory for the script"
            " (default: ~/.cytoscape-ai/tmp)."
        ),
    )
    p.add_argument("--stream", action="store_true", help="Stream output instead of a JSON result.")
    return p


def _run(args: argparse.Namespace) -> dict:
    try:
        script_path = str(pathlib.Path(args.script).resolve())
        if not os.path.isfile(script_path):
            raise FileNotFoundError("Script not found: " + script_path)
        workdir_path = (pathlib.Path(args.workdir) if args.workdir else _app_tmp_dir()).resolve()
        if not workdir_path.is_dir():
            raise NotADirectoryError("Workdir not found: " + str(workdir_path))
        if args.timeout <= 0 or not math.isfinite(args.timeout):
            raise ValueError("Timeout must be a positive finite number")
        if args.stream:
            _run_streaming(script_path, args.script_args, args.timeout, str(workdir_path))
        return _run_in_process(script_path, args.script_args, args.timeout, str(workdir_path))
    except Exception as exc:
        return _result("error", "", str(exc), 1, 0)


def _run_in_process(script_path: str, extra_args: list,
                    timeout_sec: float, workdir: str) -> dict:
    """Capture output; return partial output if the worker times out."""
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    exit_code_ref = [0]
    done_event = threading.Event()

    saved_argv = sys.argv[:]
    saved_cwd = os.getcwd()

    def target():
        try:
            sys.argv = [script_path] + list(extra_args)
            os.chdir(workdir)
            with contextlib.redirect_stdout(stdout_buf), \
                 contextlib.redirect_stderr(stderr_buf):
                runpy.run_path(script_path, run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                exit_code_ref[0] = 0
            elif isinstance(code, int):
                exit_code_ref[0] = code
            else:
                exit_code_ref[0] = 1
        except BaseException:  # noqa: BLE001
            stderr_buf.write(traceback.format_exc())
            exit_code_ref[0] = 1
        finally:
            try:
                sys.argv = saved_argv
                os.chdir(saved_cwd)
            except Exception:  # noqa: BLE001
                pass
            done_event.set()

    worker = threading.Thread(target=target, daemon=True)
    start = time.monotonic()
    worker.start()
    finished = done_event.wait(timeout=timeout_sec)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    if not finished:
        return _result(
            "timeout",
            stdout_buf.getvalue(),
            stderr_buf.getvalue(),
            -1,
            elapsed_ms,
        )

    rc = exit_code_ref[0]
    status = "success" if rc == 0 else "error"
    return _result(status, stdout_buf.getvalue(), stderr_buf.getvalue(), rc, elapsed_ms)


def _run_streaming(script_path: str, extra_args: list,
                   timeout_sec: float, workdir: str) -> None:
    """Stream output; exit with the script code or 124 on timeout."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
        except Exception:  # noqa: BLE001
            pass
    exit_code_ref = [0]
    done_event = threading.Event()

    def target():
        try:
            sys.argv = [script_path] + list(extra_args)
            os.chdir(workdir)
            runpy.run_path(script_path, run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            exit_code_ref[0] = code if isinstance(code, int) else (0 if code is None else 1)
        except BaseException:  # noqa: BLE001
            sys.stderr.write(traceback.format_exc())
            exit_code_ref[0] = 1
        finally:
            done_event.set()

    threading.Thread(target=target, daemon=True).start()
    finished = done_event.wait(timeout=timeout_sec)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code_ref[0] if finished else 124)


def _emit_and_exit(payload: str) -> None:
    """Bypass timed-out output redirects and exit without waiting for the worker."""
    sys.__stdout__.reconfigure(encoding="utf-8")
    sys.__stdout__.write(payload + "\n")
    sys.__stdout__.flush()
    os._exit(0)


def _result(status: str, stdout: str, stderr: str,
            exit_code: int, runtime_ms: int) -> dict:
    return {
        "status":     status,
        "stdout":     stdout or "",
        "stderr":     stderr or "",
        "exit_code":  exit_code,
        "runtime_ms": runtime_ms,
    }


def main() -> None:
    if sys.argv[1:2] == ["--licenses"]:
        root = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent / "build"))
        notices = root / ("licenses" if getattr(sys, "frozen", False) else "legal") / "THIRD-PARTY-NOTICES.txt"
        if not notices.is_file():
            sys.stderr.write("License materials are missing; prepare them before building.\n")
            sys.exit(1)
        # License authors' names must survive Windows's legacy pipe encoding.
        sys.stdout.reconfigure(encoding="utf-8")
        print(notices.read_text(encoding="utf-8"), flush=True)
        return
    if sys.argv[1:2] == ["--version"]:
        print(json.dumps({"runner_version": RUNNER_VERSION,
                          "python": sys.version.split()[0],
                          "stream": True}), flush=True)
        return
    argv = sys.argv[1:]
    separator = argv.index("--") if "--" in argv else len(argv)
    args = _build_parser().parse_args(argv[:separator])
    args.script_args = argv[separator + 1:]
    result = _run(args)
    if args.stream:
        sys.stderr.write(result["stderr"] + "\n")
        sys.exit(result["exit_code"])
    _emit_and_exit(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
