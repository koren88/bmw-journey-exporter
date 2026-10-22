# Accessibility

BMW Journey Exporter is a terminal-based command-line tool. Setup instructions
and copyable commands are in the [README](README.md#requirements); Docker/Make
and local Python setup are both documented there.

Phone capture also depends on the Android My BMW app in English, with the
supported journey-list screen open. The tool reads that screen through ADB and
UI XML; it does not provide an alternate graphical capture interface.

Screen-reader and other assistive-technology compatibility has not been
formally tested. To report an accessibility barrier, open a
[GitHub issue](https://github.com/koren88/bmw-journey-exporter/issues) and
include the task, platform, and observed barrier. Assistive-technology details
are optional. You do not need to disclose a disability, provide screenshots,
or share personal journey data.
