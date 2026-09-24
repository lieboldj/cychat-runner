Python runners downloaded automatically by CyChat for Linux x86-64, Windows x86-64, and macOS Apple Silicon/Intel.

2.1.0: the Windows runner is one folder, shipped as `script-runner-windows-x86_64.zip`
and unpacked once by CyChat, instead of an exe that unpacked itself into `%TEMP%` on
every start. Package tests, C headers and type stubs are left out of it. The other
three runners are built as before.

Executables are distributed under GPLv3; original runner code is MIT-licensed.
Matching `.licenses.zip` files contain notices and build inventories. Dependency
and project sources are provided in `runner-2.1.0-sources.tar.gz`, with Linux
system-library sources in the separate `.system-sources.tar.gz` archive.

`checksums.properties` contains the four runner hashes (the Windows one is the zip's) used by CyChat;
`SHA256SUMS` covers all other release assets. Source archives are not needed to
run CyChat.
