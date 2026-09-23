# Microsoft Windows runtime components

The Windows build uses the Microsoft Visual C++ runtime and Universal CRT.
Microsoft retains the copyright and licensing of these system components;
the project's MIT and combined-work GPLv3 notices do not relicense them.
These compiler/operating-system runtime components are treated as System
Libraries under GPLv3, rather than as project source covered by its source offer.

The build inventory identifies the actual DLLs and their hashes. Only release
runtime files are permitted; debug runtimes and unrelated Microsoft binaries
must not be copied. Redistribution rights derive from the applicable Microsoft
software license, not from this notice.

Microsoft's redistribution rules and file list:

* https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
* https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution
* https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist

The Python distribution's own license notice is also included in the license
archive.
