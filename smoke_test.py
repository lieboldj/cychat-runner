#!/usr/bin/env python3
"""Check a built binary: python smoke_test.py dist/script-runner."""
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from runner import RUNNER_VERSION


def run(cmd, stdin=None, timeout=180, encoding=None):
    return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout, encoding=encoding)


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  " + detail[:600]))
    if not ok:
        sys.exit(1)


def main():
    binary = str(Path(sys.argv[1]).resolve())
    work = Path(tempfile.mkdtemp(prefix="runner smoke "))

    r = run([binary, "--help"])
    check("--help exits 0 (CyChat health check)", r.returncode == 0, r.stderr)

    r = run([binary, "--version"])
    info = json.loads(r.stdout)
    check("--version reports runner 2 with streaming", info.get("stream") is True and info.get("runner_version") == RUNNER_VERSION, r.stdout)
    print("     ", info)

    r = run([binary, "--licenses"], encoding="utf-8")
    check("license notices and source instructions are available offline",
          r.returncode == 0 and all(text in r.stdout for text in
              ("GNU GENERAL PUBLIC LICENSE", "MIT License", "igraph", "chardet", "source")),
          r.stderr)

    arguments = work / "script with spaces.py"
    arguments.write_text("import json,sys\nprint(json.dumps(sys.argv[1:]))\n")
    values = [str(arguments), r"C:\Users\Jane Doe\script.py", "", "--version", "--licenses"]
    r = run([binary, "--script", str(arguments), "--workdir", str(work), "--", *values])
    envelope = json.loads(r.stdout)
    check("script arguments survive spaces, Windows paths, and option names",
          envelope["status"] == "success" and json.loads(envelope["stdout"]) == values, r.stdout)

    imports = work / "imports.py"
    imports.write_text(
        "import py4cytoscape, ndex2, pandas, numpy, networkx, igraph, requests, json, re\n"
        "print(pandas.__version__, numpy.__version__, networkx.__version__, igraph.__version__)\n")
    r = run([binary, "--script", str(imports), "--timeout", "120", "--workdir", str(work)])
    env = json.loads(r.stdout)
    check("bundled packages import", env["status"] == "success", env.get("stderr", ""))
    print("     ", env["stdout"].strip())

    slow = work / "slow.py"
    slow.write_text("import time\nprint('before')\ntime.sleep(30)\n")
    started = time.monotonic()
    r = run([binary, "--script", str(slow), "--timeout", "3", "--workdir", str(work)])
    env = json.loads(r.stdout) if r.stdout.strip() else {}
    check("timeout returns an envelope with the partial output",
          env.get("status") == "timeout" and "before" in env.get("stdout", ""), repr(r.stdout))
    check("timeout returns promptly", time.monotonic() - started < 25)

    worker = work / "worker.py"
    worker.write_text(
        "import sys, json\n"
        "print(json.dumps({'status': 'ready'}))\n"
        "for line in sys.stdin:\n"
        "    print(json.dumps({'echo': line.strip()}))\n"
        "    break\n")
    proc = subprocess.Popen([binary, "--script", str(worker), "--stream", "--timeout", "60",
                             "--workdir", str(work)],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    ready = proc.stdout.readline()
    check("--stream delivers the ready line before stdin is closed",
          json.loads(ready).get("status") == "ready", ready)
    proc.stdin.write("ping\n")
    proc.stdin.flush()
    echo = proc.stdout.readline()
    check("--stream round-trips a request", json.loads(echo).get("echo") == "ping", echo)
    proc.wait(timeout=30)
    print("all checks passed")


if __name__ == "__main__":
    main()
