# Dependency licenses and sources for runner 2.0.0

License terms and source provenance for the packaged runners.

## Python dependencies

`python-packages.json` records exact versions, upstream source locations and
SHA-256 values, approved installation artifact hashes, declared license
expressions, and build/runtime roles. `requirements.txt` pins the entire resolved
Python dependency set, including platform-specific build helpers. License texts
are copied from both the actual installed distributions and source archives,
including nested third-party notices. The installed metadata is preserved.

Component licenses:

| Component | Terms and treatment |
| --- | --- |
| Original runner code | MIT; preserve its existing grant and copyright notices. |
| igraph 0.11.6 / C igraph 0.10.13 | GPL-2.0-or-later; exercise the GPLv3 option for the combined executable. The sdist contains the C source and vendored dependencies, including their licenses. |
| chardet 5.2.0 | LGPL-2.1-or-later; provide its source and notices and permit modification/rebuilding. |
| certifi 2026.2.25 | MPL-2.0; provide the exact unmodified source and license. |
| NumPy 1.26.4 | BSD source plus the native-component terms in its platform-specific wheel license. |
| PyArrow 21.0.0 | Apache-2.0 plus bundled third-party terms; provide full Arrow C++ source and its upstream dependency source set, not only the Python wrapper. |
| PyInstaller 6.15.0 | GPL with the bootloader exception; retain its COPYING text. This exception does not waive other packages' obligations. |

MIT/BSD/ISC/Apache/PSF/Boost/Zlib components retain their original licenses. The
GPLv3 combined-work terms do not erase permissive grants on separable source.
Optional dependencies and build-only source included conservatively in the source
archive are not necessarily present in the executable. Native and Python module
inventories identify what PyInstaller actually selected.

## Native sources and provenance

* CPython 3.12.14 (Linux) and 3.12.10 (Windows/macOS): the official source archives,
  including platform build scripts.
  Additional Windows/macOS sources match the versions in `PCbuild/get_externals.bat`
  and `Mac/BuildScript/build-installer.py`. Preserve the installed interpreter's
  combined license when available.
* NumPy OpenBLAS: upstream revision `c2f4bdbb` (0.3.23-293), as recorded by NumPy
  1.26.4's `tools/openblas_support.py`. Preserve the wheel's complete OpenBLAS,
  LAPACK and compiler-runtime notices, and include upstream build recipes.
* Linux libquadmath: the original library's SHA-256 is
  `96973f995bad4e4b80eaa188b7bac60bd0df44b22ee67bd046b3aa4ecb9e34fd`.
  It matches the library extracted from CentOS's
  `libquadmath-4.8.5-44.el7.x86_64.rpm`. The wheel's `96973f99` name records that
  original hash before auditwheel's relocation changes. Include the matching
  `gcc-4.8.5-44.el7.src.rpm`, with distribution patches/spec, for LGPL source access.
* macOS libquadmath/libgfortran: the `gf_c469a42` (Intel) and `gf_5272328` (ARM)
  toolchain identifiers in NumPy's OpenBLAS recipe resolve through
  `MacPython/gfortran-install` to `isuruf/gcc` release `gcc-11.3.0-2`. Include that
  fork's source commit `2d280e7eafc086e9df85f50ed1a6526d6a3a204d`, including its
  Darwin patches, and the compiler installation recipe.
* GCC runtimes covered by the GCC Runtime Library Exception retain that notice.
  Linux libgfortran's wheel provenance and runtime exception are recorded
  separately from the GCC 4.8.5 libquadmath source.
* Windows OpenBLAS identifies GCC 10.3.0 in its filename. Its compiler runtime is
  covered by the upstream wheel's GCC exception notice; GCC 10.3.0 source is also
  included. The Windows wheel does not declare a separate libquadmath component.
* igraph's Linux wheel includes libxml2 2.9.1, XZ/liblzma 5.2.2 and libgomp.
  Preserve their source/notices in addition to igraph's sdist. The XZ command-line
  utilities' GPL terms are distinct from the liblzma library's terms.
* Linux libraries copied from Ubuntu are attributed using `dpkg-query`. The build
  downloads their exact source package versions, including patches, into the
  platform's `.system-sources.tar.gz`.
* Microsoft runtime DLLs retain their own terms as system/compiler components;
  see `MICROSOFT-RUNTIME.md`. They are not described as GPL-licensed project code.

`native-sources.json` preserves the source archive hashes. Arrow dependency
versions/hashes include Arrow 21.0.0's `cpp/thirdparty/versions.txt` fallback set
and the actual wheel recipe's vcpkg commit
`f7423ee180c4b7f40d43402c2feb3859161ef625`, with Arrow's `ci/vcpkg/ports.patch`.
The latter source set was resolved using the wheel's Flight, GCS, JSON, ORC,
Parquet, S3 and Azure features, plus Windows's Boost multiprecision dependency.
vcpkg checked downloads against its pinned SHA-512 values before the catalog's
SHA-256 values were recorded. The vcpkg recipe archive and Arrow patch are included;
both dependency sets include optional backends and build helpers conservatively.
Every binary copied by PyInstaller has a source-component classification. Unknown
Python versions, installation artifacts, or native libraries fail the build.
