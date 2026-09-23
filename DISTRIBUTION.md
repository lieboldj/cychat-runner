# Licenses and source code

The original runner code is [MIT-licensed](LICENSE). The combined executables
are distributed under [GPLv3](licensing/GPL-3.0.txt), because they include igraph
and other third-party code. Individual components retain their licenses,
copyright notices, and the applicable PyInstaller and GCC runtime exceptions.
Use, modification, and redistribution are not restricted to CyChat.

Each release provides:

- Four platform executables and their checksums.
- Matching `.licenses.zip` files with notices and build inventories. Notices are
  also embedded in each executable, accessible with `script-runner --licenses`.
- Project and dependency source archives, including Linux system-library sources,
  with [rebuild instructions](BUILDING.md).

The matching license and source archives remain available alongside the binaries,
at no additional charge, for as long as the binaries are offered. GitHub's
automatic repository archive alone does not include the dependency sources.

You may modify and rebuild/relink LGPL components and reverse engineer the runner
to debug those modifications. Modified runners can be used directly or with a
CyChat build containing their matching checksum pins. Upstream sources retain
their original licenses; inventories distinguish build tools from bundled code.

See the [dependency license and source inventory](licensing/REVIEW.md) for details.
