Python runners downloaded automatically by CyChat for Linux x86-64, Windows x86-64, and macOS Apple Silicon/Intel.

2.2.0: the macOS runners are one folder too, shipped as
`script-runner-macos-aarch64.tar.gz` and `script-runner-macos-x86_64.tar.gz` (a tar
keeps the folder's symlinks and executable modes) and unpacked once by CyChat. The
one-file executable unpacked 257 MB into the temp folder on every start (9 to 17 s)
and left it there when killed. The Windows runner is the one-folder zip of 2.1.0;
Linux keeps its one-file executable.

Executables are distributed under GPLv3; original runner code is MIT-licensed.
Matching `.licenses.zip` files contain notices and build inventories. Dependency
and project sources are provided in `runner-2.2.0-sources.tar.gz`, with Linux
system-library sources in the separate `.system-sources.tar.gz` archive.

`checksums.properties` contains the four runner hashes (the Windows and macOS ones are the archives') used by CyChat;
`SHA256SUMS` covers all other release assets. Source archives are not needed to
run CyChat.
