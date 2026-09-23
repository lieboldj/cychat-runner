# Runner usage and maintenance

[CyChat](https://apps.cytoscape.org/apps/cychat) is the app. This repository builds its
`script-runner-*` executables. CyChat handles downloading and sandboxing.

## CLI

```sh
script-runner --script "my script.py" --workdir "/my workspace" --timeout 30 -- "an argument" --version
script-runner --version
script-runner --licenses
```

Everything after `--` becomes a separate script argument, unchanged. `--version`
and `--licenses` are commands only in the first position. The default timeout is
30 seconds; `~/.cytoscape-ai/tmp` is created only without an explicit `--workdir`.

Normal execution emits UTF-8 JSON with `status` (`success`, `error`, `timeout`),
`stdout`, `stderr`, `exit_code`, and `runtime_ms`. The runner process exits 0 after
this envelope, including script/setup errors; timeout has `exit_code: -1`.
Invalid CLI syntax exits 2. `--stream` forwards stdin/stdout/stderr, exits with the
script's status, or exits 124 on timeout. `--version` emits JSON containing
`runner_version`, `python`, and `stream: true`. This executable is not a sandbox.

## Build and modify

Use a Git checkout and CPython 3.12.14 on Linux or 3.12.10 on Windows/macOS:

```sh
BUILD_PYTHON=python3.12 ./build.sh
```

Use Git Bash on Windows. The script installs the pinned dependencies, collects
notices, builds/tests the executable, and writes release files to `out/release`.
Checksum sidecars use `<sha256>  <filename>` on every platform. Linux packaging
requires the Ubuntu source repositories configured in `.github/workflows/build.yml`.

CI tests Ubuntu 22.04, Windows Server 2022, macOS 14 ARM and macOS 15 Intel.
The workflow runs on version tags or manual dispatch. `smoke_test.py` checks each
built executable before packaging; `check_version.py` validates the release version.
Targets are glibc 2.35+, Windows 10/11 x86-64 and macOS 12+; the macOS minimum comes
from the bundled libraries. Earlier OS releases are not validated. Binaries have
no publisher signature/notarization; macOS ad-hoc signatures are not a trusted
publisher identity. Gatekeeper or SmartScreen may warn on standalone downloads.

The release source archive contains this project's files, dependency archives and
upstream build instructions. Preserve their licenses when modifying them. To
replace a component, build/install its modified source in `.venv`, then run
`python release_materials.py prepare --report out/install-report.json --development`
and `python -m PyInstaller script-runner.spec --clean --noconfirm`.
Development builds cannot pass release verification. For a reviewed release,
update the version/hash catalogs to match your sources and installation artifacts.
Modified binaries can run independently, or with their matching pins in your
CyChat build; no signing key is required to rebuild them.

Native builds may need C/C++/Fortran tools. igraph's sdist includes its C sources;
PyArrow also needs the full Arrow archive and its `ci/scripts/python_wheel_*`
recipes. Use the included vcpkg snapshot plus Arrow's `ci/vcpkg/ports.patch`.
NumPy's OpenBLAS/compiler sources and build recipes are included; unpack the Linux
GCC source RPM with `rpm2cpio`/`cpio` or `bsdtar` and follow its spec file. The macOS
GCC source includes Darwin patches. See `licensing/REVIEW.md` for provenance.

## Release

1. Set `RUNNER_VERSION` and release notes. Review licensing when dependencies change. Commit, tag `v<VERSION>` and push.
2. CI builds/tests all four runners from that tag and prepares a verified **draft**
   with licenses, sources and checksums. Manual dispatch defaults to `runner.py`.
3. Test the draft binaries with a CyChat build that pins their checksums.
4. Publish the verified draft with its source/license assets. Publishing does
   not change the binary hashes. Draft URLs cannot serve normal CyChat downloads.
5. Release the CyChat version that pins the published checksums. Keep the
   matching source archives available alongside the executables.
