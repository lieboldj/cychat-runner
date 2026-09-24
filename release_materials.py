"""Create auditable, hash-checked source, notice, and binary inventories.

Uses only the standard library, so it can also verify downloaded releases.
The reviewed catalogs are inputs, never inferred from a successful build.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fnmatch
import gzip
import hashlib
import http.client
from importlib import metadata
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "out/source-cache"
LEGAL = ROOT / "build/legal"
ASSETS = (
    "script-runner-linux-x86_64", "script-runner-windows-x86_64.zip",
    "script-runner-macos-aarch64.tar.gz", "script-runner-macos-x86_64.tar.gz",
)
CPYTHON_SOURCE = "cpython" if sys.platform.startswith("linux") else "cpython-desktop"


def canonical(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def anonymous_tar_member(member):
    """Keep local account names and IDs out of published archive headers."""
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    for key in ("uid", "gid", "uname", "gname"):
        member.pax_headers.pop(key, None)
    return member


def catalogs():
    packages = read_json(ROOT / "licensing/python-packages.json")
    native = read_json(ROOT / "licensing/native-sources.json")
    sources = {name: item["source"] for name, item in packages.items()}
    for name, item in native.items():
        if name in sources:
            raise ValueError("Duplicate source id: " + name)
        sources[name] = item["source"]
    return packages, native, sources


def _download_source_once(item):
    name, record = item
    filename = record["filename"]
    if PurePosixPath(filename).name != filename or "\\" in filename:
        raise ValueError("Unsafe source filename")
    if not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
        raise ValueError("Source has no reviewed checksum: " + name)
    path = CACHE / filename
    if path.exists() and sha256(path) == record["sha256"]:
        return path
    if not record["url"].startswith("https://"):
        raise ValueError("Source URL must use HTTPS")
    CACHE.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(record["url"], headers={"User-Agent": "cychat-runner-source-bundler"})
    with tempfile.NamedTemporaryFile(dir=CACHE, delete=False) as temporary:
        temp = Path(temporary.name)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                shutil.copyfileobj(response, temporary)
            temporary.close()
            if sha256(temp) != record["sha256"]:
                raise ValueError("Source checksum mismatch: " + name)
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    return path


def download_source(item):
    for attempt in range(3):
        try:
            return _download_source_once(item)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead):
            if attempt == 2:
                raise
            print("Retrying source download:", item[0], flush=True)
            time.sleep(2 * (attempt + 1))


def seed_sources(archive_path, version):
    """Reuse the source job's archives; never unpack archive-controlled paths."""
    _, _, sources = catalogs()
    wanted = {f"runner-{version}/sources/{r['filename']}": r for r in sources.values()}
    CACHE.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r|*") as archive:
        for member in archive:
            if member.isfile() and member.name in wanted:
                record = wanted.pop(member.name)
                path = CACHE / record["filename"]
                with path.open("wb") as output:
                    shutil.copyfileobj(archive.extractfile(member), output)
                if sha256(path) != record["sha256"]:
                    raise ValueError("Source checksum mismatch: " + member.name)
    if wanted:
        raise ValueError("Source archive is incomplete")


def get_sources(sources):
    filenames = [item["filename"] for item in sources.values()]
    if len(filenames) != len(set(filenames)):
        raise ValueError("Source filename collision")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(download_source, sources.items()))


def is_notice(name):
    return bool(re.match(r"(?i)^(licen[sc]e|copying|notice|copyright)([._-].*|$)", PurePosixPath(name).name))


def archive_notices(path):
    """Read notices without extracting untrusted archives onto the filesystem."""
    if path.suffix in {".rpm", ".patch"}:
        return  # Source RPM is retained intact, with spec, sources and patches.
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if not member.is_dir() and is_notice(member.filename):
                    yield member.filename, archive.read(member)
    else:
        with tarfile.open(path, "r|*") as archive:
            for member in archive:
                if member.isfile() and is_notice(member.name):
                    yield member.name, archive.extractfile(member).read()


def save_notice(group, original_name, data):
    # Preserve the original archive path in a header; hash avoids basename collisions.
    name = hashlib.sha256(original_name.encode()).hexdigest()[:16] + "-" + PurePosixPath(original_name).name
    destination = LEGAL / "notices" / group / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(("Original file: " + original_name + "\n\n").encode() + data)


def prepare(report, development=False):
    packages, native, sources = catalogs()
    if platform.python_version() != native[CPYTHON_SOURCE]["version"] and not development:
        raise ValueError("Use the reviewed CPython version " + native[CPYTHON_SOURCE]["version"])
    installed = {canonical(d.metadata["Name"]): d for d in metadata.distributions()}
    if LEGAL.exists():
        shutil.rmtree(LEGAL)
    LEGAL.mkdir(parents=True)
    inventory = []
    for name, dist in sorted(installed.items()):
        if name not in packages or dist.version != packages[name]["version"]:
            if not development:
                raise ValueError(f"Unreviewed package/version: {name}=={dist.version}")
            continue
        item = packages[name]
        inventory.append({"name": name, "version": dist.version, "license": item["license"],
                          "role": item["role"], "source": item["source"]})
        for file in dist.files or []:
            if is_notice(str(file)) and dist.locate_file(file).is_file():
                save_notice(name, str(file), dist.locate_file(file).read_bytes())
        # Preserve metadata declarations too (e.g. wget's public-domain dedication).
        save_notice(name, "METADATA", dist.read_text("METADATA").encode())
    install = read_json(report)
    for item in install["install"]:
        name = canonical(item["metadata"]["name"])
        artifact_hash = item["download_info"]["archive_info"].get("hashes", {}).get("sha256")
        if name not in packages or artifact_hash not in packages[name]["artifacts"].values():
            if not development:
                raise ValueError("Unreviewed installation artifact: " + name)
    get_sources(sources)
    for name, record in sources.items():
        for original, content in archive_notices(CACHE / record["filename"]):
            save_notice(name, original, content)
    for file in ["LICENSE", "DISTRIBUTION.md", "BUILDING.md", "licensing/GPL-3.0.txt", "licensing/LGPL-2.1.txt",
                 "licensing/REVIEW.md", "licensing/python-packages.json", "licensing/native-sources.json"]:
        shutil.copyfile(ROOT / file, LEGAL / Path(file).name)
    # Preserve the interpreter distribution's own combined notice, when supplied.
    for candidate in (Path(sys.base_prefix) / "LICENSE.txt", Path(sys.base_prefix) / "LICENSE"):
        if candidate.is_file():
            save_notice("cpython-installed", candidate.name, candidate.read_bytes())
    if sys.platform.startswith("linux"):
        for name in ("libbz2-1.0", "libffi8", "liblzma5", "libsqlite3-0", "libssl3",
                     "libstdc++6", "libgcc-s1", "libuuid1", "libyajl2", "zlib1g", "libexpat1"):
            path = Path("/usr/share/doc") / name / "copyright"
            if path.is_file():
                save_notice("linux-system", name + "-copyright", path.read_bytes())
        for path in Path("/usr/share/common-licenses").glob("*"):
            if path.is_file():
                save_notice("linux-system", path.name, path.read_bytes())
    if sys.platform == "win32":
        shutil.copyfile(ROOT / "licensing/MICROSOFT-RUNTIME.md", LEGAL / "MICROSOFT-RUNTIME.md")
    write_json(LEGAL / "packages.json", inventory)
    write_json(LEGAL / "sources.json", sources)
    write_json(LEGAL / "install-report.json", install)
    write_json(LEGAL / "environment.json", {
        "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "runner_image": os.environ.get("ImageOS"), "runner_image_version": os.environ.get("ImageVersion"),
        "development": development,
    })
    with (LEGAL / "THIRD-PARTY-NOTICES.txt").open("w", encoding="utf-8", newline="\n") as output:
        output.write((ROOT / "DISTRIBUTION.md").read_text() + "\n\n")
        output.write("Source: the runner-VERSION-sources.tar.gz asset alongside this release.\n")
        output.write("https://github.com/lieboldj/cychat-runner/releases\n\n")
        for path in sorted(LEGAL.rglob("*")):
            if path.is_file() and path.name != "THIRD-PARTY-NOTICES.txt":
                output.write("\n===== " + path.relative_to(LEGAL).as_posix() + " =====\n")
                output.write(path.read_text(encoding="utf-8", errors="replace") + "\n")
    print(f"Prepared notices and sources for {len(inventory)} installed distributions.")


def record_analysis(binaries, pure):
    """Called by the spec after Analysis: record the actual bundled files."""
    if not (LEGAL / "THIRD-PARTY-NOTICES.txt").is_file():
        raise ValueError("Run release_materials.py prepare before building")
    owners = {}
    for dist in metadata.distributions():
        name = canonical(dist.metadata["Name"])
        for file in dist.files or []:
            owners[Path(dist.locate_file(file)).resolve()] = name
    records = []
    for destination, source, kind in binaries:
        if kind == "SYMLINK":
            records.append({"destination": destination, "kind": kind, "target": source})
            continue
        source = Path(source)
        records.append({"destination": destination.replace("\\", "/"), "kind": kind,
                        "source_path": str(source), "sha256": sha256(source),
                        "package": owners.get(source.resolve()), "size": source.stat().st_size})
        records[-1]["source_components"] = native_components(records[-1], sys.base_prefix)
    write_json(ROOT / "build/native-inventory.json", records)
    write_json(ROOT / "build/module-inventory.json", [
        {"module": name, "package": owners.get(Path(source).resolve())}
        for name, source, kind in pure if source
    ])


def native_components(record, python_prefix):
    """Classify every copied binary; unexpected native libraries stop a release."""
    name = PurePosixPath(record["destination"]).name.lower()
    owner = record["package"]
    microsoft = ("api-ms-win-*.dll", "ucrtbase.dll", "msvcp140*.dll", "vcruntime140*.dll", "vcomp140.dll")
    if sys.platform == "win32" and any(fnmatch.fnmatch(name, p) for p in microsoft):
        return ["microsoft-system-runtime"]
    if owner:
        if owner == "numpy" and any(x in name for x in ("openblas", "gfortran", "quadmath", "libgcc")):
            if sys.platform.startswith("linux"):
                component = "linux-gcc" if "quadmath" in name else ("openblas" if "openblas" in name else "gcc-runtime-exception")
            else:
                component = "windows-gcc" if sys.platform == "win32" else "macos-gcc"
            return ["numpy", "openblas", component]
        if owner == "pyarrow":
            return ["pyarrow", "apache-arrow-cpp"] + [n for n in catalogs()[1] if n.startswith("arrow-")]
        if owner == "igraph" and "libxml" in name:
            return ["igraph", "libxml2-igraph"]
        if owner == "igraph" and "liblzma" in name:
            return ["igraph", "xz-igraph"]
        if owner == "igraph" and "libgomp" in name:
            return ["igraph", "linux-gcc"]
        return [owner]
    if sys.platform.startswith("linux") and name.startswith(("libcrypto", "libssl", "libffi", "liblzma", "libbz2", "libsqlite", "libstdc++", "libgcc_s", "libuuid", "libyajl", "libz.", "libexpat")):
        return ["linux-system-source"]
    if name.startswith(("libcrypto", "libssl")):
        return ["openssl-cpython"]
    if name.startswith("libffi"):
        return ["libffi-cpython"]
    if name.startswith("sqlite3"):
        return ["sqlite-cpython"]
    source = Path(record["source_path"]).resolve()
    if source.is_relative_to(Path(python_prefix).resolve()):
        if record["kind"] == "EXTENSION" or name.startswith(("libpython3.12", "python3")) or name == "python":
            return [CPYTHON_SOURCE]
    raise ValueError("Unreviewed native library: " + record["destination"])


def linux_sources(records, output, asset):
    """Keep exact Ubuntu source packages, including distro patches/specifications."""
    packages = set()
    sources = set()
    for record in records:
        if "linux-system-source" not in record.get("source_components", []):
            continue
        filename = record["source_path"]
        found = None
        for candidate in (filename, "/usr" + filename if filename.startswith("/lib/") else filename.removeprefix("/usr")):
            result = subprocess.run(["dpkg-query", "-S", candidate], capture_output=True, text=True)
            if result.returncode == 0:
                found = result.stdout.split(": ", 1)[0]
                break
        if not found:
            raise ValueError("No Debian source owner for " + filename)
        packages.add(found)
        query = subprocess.check_output(["dpkg-query", "-W", "-f=${source:Package}\t${source:Version}", found], text=True)
        name, version = query.split("\t")
        sources.add((name, version))
        record["system_package"] = found
        record["system_source"] = {"name": name, "version": version}
    if not sources:
        return None
    directory = ROOT / "out/system-sources"
    directory.mkdir(parents=True, exist_ok=True)
    for name, version in sorted(sources):
        subprocess.run(["apt-get", "source", "--download-only", "--only-source", name + "=" + version], cwd=directory, check=True)
    write_json(directory / "packages.json", [{"name": n, "version": v} for n, v in sorted(sources)])
    write_json(directory / "checksums.json", {p.name: sha256(p) for p in sorted(directory.iterdir()) if p.is_file() and p.name != "checksums.json"})
    archive = output / (asset + ".system-sources.tar.gz")
    with tarfile.open(archive, "w:gz") as bundle:
        for path in sorted(directory.iterdir()):
            if path.is_file():
                bundle.add(path, arcname=path.name, filter=anonymous_tar_member)
    return {"filename": archive.name, "sha256": sha256(archive)}


def package(asset, binary):
    if asset not in ASSETS:
        raise ValueError("Unknown release asset")
    output = ROOT / "out/release"
    output.mkdir(parents=True, exist_ok=True)
    destination = output / asset
    if asset.endswith(".zip"):
        zip_folder(Path(binary), destination)
    elif asset.endswith(".tar.gz"):
        tar_folder(Path(binary), destination)
    else:
        shutil.copyfile(binary, destination)
    digest = sha256(destination)
    destination.with_name(asset + ".sha256").write_text(f"{digest}  {asset}\n", encoding="utf-8", newline="\n")
    environment = read_json(LEGAL / "environment.json")
    records = read_json(ROOT / "build/native-inventory.json")
    system_source = linux_sources(records, output, asset) if sys.platform.startswith("linux") else None
    # Absolute build paths are needed locally for source lookup, not in releases.
    public_records = [{key: value for key, value in record.items() if key != "source_path"}
                      for record in records]
    report = {"asset": asset, "sha256": digest, "size": destination.stat().st_size,
              "environment": environment, "packages": read_json(LEGAL / "packages.json"),
              "native_files": public_records, "system_source_archive": system_source,
              "python_modules": read_json(ROOT / "build/module-inventory.json")}
    write_json(output / (asset + ".build-info.json"), report)
    with zipfile.ZipFile(output / (asset + ".licenses.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(LEGAL.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(LEGAL).as_posix())
        archive.write(output / (asset + ".build-info.json"), "build-info.json")
    print(asset, destination.stat().st_size, digest)


def zip_folder(folder, destination):
    """Zip a one-folder build under its folder name, byte-identical for identical input."""
    files = sorted((p for p in folder.rglob("*") if p.is_file()), key=lambda p: p.relative_to(folder).as_posix())
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(f"{folder.name}/{path.relative_to(folder).as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100755 << 16
            archive.writestr(info, path.read_bytes())


def tar_folder(folder, destination):
    """Archive a one-folder build with its symlinks and modes, byte-identical for identical input."""
    paths = [folder]
    for root, dirs, files in os.walk(folder):
        paths += [Path(root, name) for name in dirs + files]
    paths.sort(key=lambda p: p.relative_to(folder.parent).as_posix())

    def normalize(member):
        member.mtime = 0
        return anonymous_tar_member(member)

    with open(destination, "wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for path in paths:
            archive.add(path, arcname=path.relative_to(folder.parent).as_posix(), recursive=False, filter=normalize)


def source_bundle(version):
    _, _, sources = catalogs()
    get_sources(sources)
    output = ROOT / "out/release"
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"runner-{version}-sources.tar.gz"
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    with tarfile.open(path, "w:gz") as archive:
        for filename in tracked:
            if filename:
                archive.add(ROOT / filename, arcname=f"runner-{version}/project/{filename}",
                            recursive=False, filter=anonymous_tar_member)
        for name, record in sources.items():
            archive.add(CACHE / record["filename"], arcname=f"runner-{version}/sources/{record['filename']}",
                        filter=anonymous_tar_member)
        data = (json.dumps(sources, indent=2, sort_keys=True) + "\n").encode()
        member = tarfile.TarInfo(f"runner-{version}/sources.json")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    print(path.name, path.stat().st_size, sha256(path))


def verify_release(directory, version):
    directory = Path(directory)
    _, _, sources = catalogs()
    rows = []
    commits = set()
    for asset in ASSETS:
        binary = directory / asset
        digest, filename = (directory / (asset + ".sha256")).read_text().split()
        if filename != asset or sha256(binary) != digest:
            raise ValueError("Binary checksum mismatch: " + asset)
        report = read_json(directory / (asset + ".build-info.json"))
        if report["sha256"] != digest or report["environment"]["development"]:
            raise ValueError("Unreviewed build: " + asset)
        commit = report["environment"].get("commit", "")
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Missing build commit: " + asset)
        commits.add(commit)
        system_source = report.get("system_source_archive")
        if system_source and sha256(directory / system_source["filename"]) != system_source["sha256"]:
            raise ValueError("System source archive mismatch")
        for record in report["native_files"]:
            if record["kind"] != "SYMLINK" and not record.get("source_components"):
                raise ValueError("Unreviewed native binary")
            for component in record.get("source_components", []):
                if component not in sources and component not in {"linux-system-source", "microsoft-system-runtime", "gcc-runtime-exception"}:
                    raise ValueError("Missing native source: " + component)
        with zipfile.ZipFile(directory / (asset + ".licenses.zip")) as archive:
            for required in ("THIRD-PARTY-NOTICES.txt", "GPL-3.0.txt", "LICENSE", "sources.json", "build-info.json"):
                if not archive.read(required):
                    raise ValueError("Empty licensing material: " + required)
        rows.append(f"{asset}.sha256={digest}")
    if len(commits) != 1:
        raise ValueError("Release binaries come from different commits")
    source = directory / f"runner-{version}-sources.tar.gz"
    with tarfile.open(source) as archive:
        for record in sources.values():
            member = archive.extractfile(f"runner-{version}/sources/{record['filename']}")
            if hashlib.file_digest(member, "sha256").hexdigest() != record["sha256"]:
                raise ValueError("Release source mismatch: " + record["filename"])
    rows.append(f"runner.version={version}")
    (directory / "checksums.properties").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    files = sorted(p for p in directory.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (directory / "SHA256SUMS").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in files), encoding="utf-8", newline="\n")
    print("Verified four binaries, license archives, source archives, and checksums.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--report", required=True)
    prepare_parser.add_argument("--development", action="store_true")
    packaging = commands.add_parser("package")
    packaging.add_argument("--asset", required=True)
    packaging.add_argument("--binary", required=True)
    sources = commands.add_parser("sources")
    sources.add_argument("--version", required=True)
    seed = commands.add_parser("seed")
    seed.add_argument("--archive", required=True)
    seed.add_argument("--version", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--directory", required=True)
    verify.add_argument("--version", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.report, args.development)
    elif args.command == "package":
        package(args.asset, args.binary)
    elif args.command == "sources":
        source_bundle(args.version)
    elif args.command == "seed":
        seed_sources(args.archive, args.version)
    elif args.command == "verify":
        verify_release(args.directory, args.version)


if __name__ == "__main__":
    main()
