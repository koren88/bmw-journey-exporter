# bmw-journey-exporter

An unofficial, local tool that transcribes the journey list visible in the Android My BMW app through Android Debug Bridge (ADB). It does not call BMW services or perform CarData authentication. It reads what the app currently shows and keeps the UI XML used for each capture.

**This project is unofficial and is not affiliated with, endorsed by, or connected to BMW.** Treat exports as personal records to review, not as a verified tax or accounting log. Only history that is still available in the app can be captured.

## Quick start

1. Install Android Platform Tools on the host and run `python bmw_export_journeys.py --doctor` after starting ADB.
2. Enable USB debugging on the phone, connect it, accept Android's authorization prompt, then open My BMW → vehicle → **All journeys** and select the latest month you want.
3. Capture a month range:

```sh
python3 bmw_export_journeys.py --from-month 2025-01 --to-month 2025-06 --output ./bmw-capture
```

By default, a successful export contains only `journeys.xlsx`. `--formats xlsx,csv` also writes CSV, and `--formats all` writes XLSX, CSV, JSON, and XML. Selecting fewer formats does not remove reports from an earlier run; only the selected output filenames are replaced. Exit status `0` means every requested month matched the app trip count and requested reports validated; `2` means the capture is incomplete or the CLI rejected its arguments (argparse usage errors also use `2`); `1` means runtime/preflight or report validation failed. GNU Make may report its own recipe failure status rather than preserving every underlying process exit code. Completeness status and warnings appear in the workbook's Monthly summary.

## Make quick start

GNU Make is a convenience interface on macOS and Linux. Capture, doctor, report, and merge use Docker; capture does not need Python installed on the host. Docker and host Android Platform Tools are required for phone operations. `make setup` is optional and creates a project-local `.venv` for Python use; it does not install Python, ADB, Docker, or system packages. `make test` prefers `.venv/bin/python` when available, then uses `python3`; set `PYTHON=/path/to/python` to select a specific interpreter. If the selected interpreter lacks project dependencies, Make uses the documented Docker test fallback when Docker is available.

```sh
make help
make doctor
make capture YEAR=2026 TIMEZONE=Europe/Ljubljana
make capture MONTH=2026-10 TIMEZONE=Europe/Ljubljana
make capture FROM=2026-09 TO=2026-10 TIMEZONE=Europe/Ljubljana
make capture YEAR=2026 FORMATS=xlsx,csv
make resume OUTPUT='./my-capture'
make report INPUT='./my-capture'
make merge INPUTS='./capture one:./capture two' OUTPUT='./merged capture'
make test
```

When `OUTPUT` is omitted for `make capture`, Make creates a unique `./bmw-export-<timestamp>-<pid>` directory. Resume requires an existing `OUTPUT`; selection and settings are loaded from its manifest if omitted. Explicit selection or settings that disagree with the manifest are rejected. `FORMATS` accepts `xlsx` (default), comma-separated selections such as `xlsx,csv`, or `all`. `KEEP_CAPTURE=1` retains data needed for resume, merge, and report regeneration; `KEEP_DEBUG=1` retains that data plus raw XML. Paths containing spaces are preserved. For merge, `INPUTS` is a colon-separated list; a colon inside an individual path is not supported. Make's Docker report and merge inputs must be paths inside this repository's mount, expressed relative to the repository root (for example, `INPUT='./my-capture'`). The Docker launcher mounts only the repository at `/workspace`; host paths outside it are not accessible through `make report` or `make merge`. For an external capture, use the local Python CLI alternative below. All Make actions ultimately use the Python CLI, while phone actions and offline report/merge use the shared Docker launcher. Direct CLI and `docker-macos.sh` remain available.

Equivalent direct CLI examples:

```sh
python bmw_export_journeys.py --year 2026 --timezone Europe/Ljubljana --output ./bmw-export-2026
python bmw_export_journeys.py --month 2026-10 --timezone Europe/Ljubljana --output ./bmw-october
python bmw_export_journeys.py --from-month 2026-09 --to-month 2026-10 --timezone Europe/Ljubljana --output ./bmw-sep-oct
python bmw_export_journeys.py --resume --output './existing capture'
python bmw_export_journeys.py --report-only './existing capture'
python bmw_export_journeys.py --month 2026-10 --formats xlsx,csv --output ./bmw-october
python bmw_export_journeys.py --merge './capture one' --merge './capture two' --output './merged capture'
```

The local CLI can read an existing capture anywhere the host Python process can access. After `make setup`, for example, regenerate reports from an external capture without Docker:

```sh
./.venv/bin/python bmw_export_journeys.py --report-only '/absolute/path/to/bmw-capture'
```

This local-Python command does not connect to ADB. The Docker launcher currently mounts only the repository; external host-path mounting has not been implemented or tested.

The app UI must be English and expose the exact **All journeys** label and supported package `de.bmw.connected.mobile20.row`. Other languages, app layouts, and package names are detected as unsupported. Capture one month with `--month 2025-05`, or a year with `--year 2025`. Past years include January–December; the current year includes January through the current month. Future requests are rejected. Capture navigates backward, so open the latest requested month first. The user must perform initial navigation into My BMW, the correct vehicle, **All journeys**, and that month.

## Docker on macOS (launcher provided; phone capture tested)

Docker Desktop is required. USB devices are not generally passed directly to the Linux container by Docker Desktop; for capture, the launcher connects to the host ADB server. It builds or refreshes the image when source files change, starts ADB only if no server is listening (and explains why), and verifies container-to-host connectivity before forwarding capture arguments. It does not start ADB for `--help`, `--report-only`, or `--merge`.

```sh
./docker-macos.sh --doctor
./docker-macos.sh --month 2025-05 --timezone Europe/Ljubljana --output ./bmw-capture
```

The macOS Docker capture path has now been exercised with an authorized phone. The launcher stops before capture if Docker Desktop cannot reach `host.docker.internal:5037`. The CLI does not start or reconfigure ADB; the existing macOS launcher starts ADB only when no server is listening and explains that action.

## Docker on Windows and Linux

Build the image with `docker build -t bmw-journey-exporter .` after installing Docker. Install Android Platform Tools on the host, connect the phone, and accept its authorization prompt. If you choose to start the host server, run `adb start-server` yourself after reviewing its effect. On Windows Docker Desktop, use `host.docker.internal:5037`; in PowerShell, mount an absolute Windows path, for example:

```powershell
New-Item -ItemType Directory -Force bmw-capture
docker run --rm -v "${PWD}/bmw-capture:/capture" -e ADB_SERVER_SOCKET=tcp:host.docker.internal:5037 bmw-journey-exporter --month 2025-05 --timezone Europe/Ljubljana --output /capture/run
```

On Linux, use the provided launcher with an explicit host ADB address. It uses Docker host networking, checks the ADB protocol from a container, and never starts or reconfigures the ADB server:

```sh
BMW_ADB_HOST=127.0.0.1 BMW_ADB_PORT=5037 ./docker-linux.sh --doctor
BMW_ADB_HOST=127.0.0.1 BMW_ADB_PORT=5037 ./docker-linux.sh --month 2025-05 --timezone Europe/Ljubljana --output ./bmw-capture
```

The address must already be reachable from a Linux container using `--network host`. Set `BMW_ADB_HOST` to the host/IP where the existing server listens. Do not expose the ADB server to an untrusted network. The Linux launcher's arguments and network setup have offline fake-Docker tests; real Linux phone capture has not been exercised.

The shared Docker launchers mount only this repository at `/workspace`. Capture/resume outputs and report/merge inputs must resolve inside the repository. Absolute paths inside it are translated to `/workspace/...`; paths outside it, including paths escaping through `..` or symlinks, are rejected before Docker runs. Use the local Python CLI for captures or reports stored elsewhere. On Linux, launcher containers run as the invoking user's numeric UID/GID so files written into the bind mount are not left owned by root. This UID/GID behavior has offline argument coverage but has not been exercised on a real Linux Docker host.

Windows Docker/phone capture remains unverified. Windows instructions below use native Python/PowerShell or WSL; WSL does not automatically gain access to a USB-connected phone.

## Windows native Python and WSL

GNU Make is not assumed to be installed on Windows. For native PowerShell, install Python and Android Platform Tools yourself, install project dependencies, then use the CLI directly:

```powershell
py -m pip install -r requirements.txt
adb start-server
adb devices
# Unlock and authorize the phone, then open the correct vehicle's All journeys screen.
py bmw_export_journeys.py --doctor
py bmw_export_journeys.py --from-month 2026-09 --to-month 2026-10 --timezone Europe/Ljubljana --output '.\bmw capture'
py bmw_export_journeys.py --resume --output '.\bmw capture'
py bmw_export_journeys.py --report-only '.\bmw capture'
```

For WSL, install GNU Make, Python or Docker, and Android Platform Tools inside the Linux environment as appropriate. `make capture` uses `docker-linux.sh` and requires `BMW_ADB_HOST` to name an ADB server reachable from the container. USB access from WSL is not automatic; configure and verify the phone/ADB connection in WSL before running `make doctor`. Windows native phone capture, WSL USB access, and WSL Docker networking have not been tested here.

## Compatibility and testing status

| Environment | Offline tests | Phone capture | Notes |
| --- | --- | --- | --- |
| macOS + Docker | Verified locally | Verified on an authorized phone | Doctor, uninterrupted October, interrupted/resumed October, September–October, and January–October runs completed. |
| Linux + Docker | CI and fake-launcher tests configured; real host not exercised | Unverified | Linux launcher requires explicit `BMW_ADB_HOST` and host networking. |
| Windows native | CI tests configured | Unverified | Use Python/PowerShell; Make is not assumed available. |
| WSL | Linux guidance only | Unverified | USB access and Docker networking require user setup. |

CI runs offline tests on macOS, Windows, and Linux. Those tests do not verify a physical phone, USB authorization, or Docker-to-host ADB networking.

## ADB diagnostics and phone availability

`python bmw_export_journeys.py --doctor` checks the ADB executable, an already-running ADB server, connected/authorized devices, and the supported My BMW screen. It dumps UI XML but does not tap, swipe, open the app, or navigate. It attempts to remove only its exact temporary dump file from the device; if ADB disconnects or cleanup is denied, it warns that the file may remain. Capture also removes only its own exact temporary XML file on exit. USB debugging, authorization, and initial navigation into the correct vehicle and **All journeys** screen are user actions.

The optional `--keep-awake` temporarily changes Android's screen timeout to two hours. Before changing it, the tool checkpoints the original timeout and device serial locally, then attempts restoration on normal exit, Ctrl+C, and SIGTERM. A resumed session checks for unresolved restoration records first. It carries forward the original timeout only when the selected device and current applied value match; otherwise it stops without changing the setting and provides guidance. If restoration fails, it prints a manual `adb -s SERIAL shell settings put system screen_off_timeout VALUE` command using the saved values. Restoration cannot be promised after SIGKILL, a device disconnection, or loss of ADB connectivity.

## Local Python alternative

Python 3.9 or newer, pip, and host Android Platform Tools are required for local use. Python 3.9 is the API/syntax minimum; the configured CI currently exercises Python 3.12 rather than 3.9. No Python installation is required inside the phone.

```sh
python3 -m venv .venv
. .venv/bin/activate                 # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python bmw_export_journeys.py --month 2025-05 --output ./bmw-capture
```

Use `python` instead of `python3` on Windows where appropriate. Run `python bmw_export_journeys.py --help` for all options.

## Selecting dates and devices

```sh
# One month (make sure the output directory does not already exist)
python bmw_export_journeys.py --month 2025-05 --output ./capture-may

# Inclusive month range; open June in the app before starting
python bmw_export_journeys.py --from-month 2025-01 --to-month 2025-06 --output ./capture-h1

# The macOS Docker launcher forwards timezone configuration
./docker-macos.sh --from-month 2025-01 --to-month 2025-06 --timezone Europe/Ljubljana --output ./capture-h1

# Past year; open December in the app first
python bmw_export_journeys.py --year 2025 --output ./capture-2025

# Current year through the present month; October 2026 means January–October
python bmw_export_journeys.py --year 2026 --output ./capture-2026

# Several authorized devices: select one explicitly
python bmw_export_journeys.py --month 2025-05 --serial ANDROID-DEVICE-01 --output ./capture-may
```

Month values must use `YYYY-MM`. The start month must not follow the end month. `--timezone` accepts an IANA timezone such as `Europe/Ljubljana`; it controls the saved capture date, session offsets, and which month counts as current. Without it, the host local timezone is used. The timezone is saved in session metadata and must match to resume. The Docker launcher forwards this argument. With multiple authorized devices, provide `--serial`; with one, the CLI selects it. Unauthorized and offline devices are not treated as available. The tool checks ADB state before opening the UI.

## Recovery and resume

Capture writes checkpoints and a readable source CSV under `capture-data/`, with raw XML under `capture-data/raw/` while the run is active. Existing legacy capture directories with files at their root remain supported. Keep the phone awake and on the journey list. If the screen changes, the phone locks, ADB disconnects, the process is interrupted, a month count differs, or report generation fails, recovery data is retained and the tool prints exact resume commands. Unlock the phone, reconnect/authorize ADB, reopen the same journey list and latest requested month, then resume:

```sh
python bmw_export_journeys.py --resume --output ./bmw-capture
```

`--resume` loads the saved selection and settings from `capture-data/capture-state.json` or `capture-data/manifest.json` when omitted (legacy root-level captures also work). Explicit selection and settings must agree with the manifest. It preserves each row's original capture date and source session, and continues raw XML numbering. Repeated identical rows can make a UI boundary ambiguous, in which case resume stops safely. Grouped rows stay grouped.

Merged selections may intentionally be non-contiguous; only months named in the source selections are included. Merged datasets support report generation and further merging, but not phone resume. Resume on a merged dataset is rejected with an explanation.

After all requested months are complete, app counts match, and every selected report has been saved and validated, temporary capture data is removed by default. Only files owned by the capture session are eligible for cleanup; unrelated files are preserved. Interrupted, failed, incomplete, and report-validation-failure runs always retain recovery data. Successful `--keep-capture` exports preserve checkpoint/CSV/manifest data without raw XML. `--keep-debug` implies `--keep-capture` and preserves raw XML too. Without `--keep-capture`, generating additional formats later or merging this export later is not possible; choose retention when starting the capture. Existing user capture directories are never automatically migrated or cleaned up.

A `complete` month means represented trip counts match the app's monthly total and the list bottom was detected. `incomplete` means a mismatch or interrupted capture; `failed` means no usable capture was produced; `pending` means requested but not attempted. Every requested month appears in the XLSX summary with its status and warnings. A genuinely empty month has zero entries and a zero app trip count. Never treat a partial month as complete. When capture data is retained, `capture-data/checks.json` is the machine-readable status record.

## Merge existing captures

Merge capture directories in list order. Session IDs and stable opaque source capture identifiers are retained for provenance; absolute host directory paths are not copied into public exports:

```sh
python bmw_export_journeys.py --merge ./capture-a --merge ./capture-b --output ./merged-capture
```

The default `--conflict error` refuses uncertain ordering, different source values for overlapping entries, or conflicting app totals. Choose `--conflict keep-first` or `--conflict keep-last` to record an explicit resolution for conflicting source values. Ambiguous identical-row boundaries remain an error because UI text alone cannot prove which identical row is the same trip. The output folder must be new.

A merged month is complete only when at least one individually complete source proves full coverage (its rows represent its expected app count), the sequence alignment is proven, and the merged rows still match the selected expected count. Partial sources may extend or overlap that proven complete sequence. Matching totals across partial sources alone never prove completeness.

## Reports without a phone

Regenerate reports from an existing capture folder offline. XLSX is the default. The versioned `capture-data/capture-state.json` is preferred when present; older portable captures can use root-level `capture.csv` or `journeys.csv` with `checks.json`. Select formats with `--formats xlsx,csv` or `--formats all`:

```sh
python bmw_export_journeys.py --report-only ./bmw-capture --formats all
```

This reads saved capture data and does not invoke ADB. It writes only the selected reports into that directory and preserves any other previously generated report files. A normal successful capture leaves `journeys.xlsx` only; use `--keep-capture` when you need to regenerate other formats later or merge the capture with another saved export.

- **XLSX:** `Monthly summary` is first, followed by chronological `YYYY-MM` sheets, including requested months with no rows. Counts, distance, and duration use numeric cells; resolved dates use date cells with the displayed source text alongside them. Headers are styled and frozen, filters and readable widths are set, grouped rows are highlighted, and monthly totals are included. BMW distance remains separate from summed displayed distances because rounding differs. Workbook relationships/styles are checked and openpyxl reopens the workbook before report files replace earlier ones.
- **CSV:** one row per captured list entry, with source fields, capture date, resolved date and date provenance. Source strings are preserved verbatim; spreadsheet software may interpret cells beginning with `=`, `+`, `-`, or `@` as formulas. For opening in Excel, prefer the XLSX report, which writes source strings as literal text. Canonical source values are not altered.
- **JSON:** entries plus monthly checks.
- **XML:** one `entry` element per captured list entry.

The displayed date/time is retained verbatim. Full and abbreviated weekdays, `THIS WEEK`, `LAST WEEK`, and explicit `WEEK OF` headings are resolved only when consistent with that row's saved capture date. A missing capture date is never silently replaced by today's date. `date_basis` marks derived, contradictory, or unresolved values. Start locations, departure times, arrival times, and trip legs are not inferred. Captures contain list entries, not necessarily individual trips.

Optional label substitutions apply only to the added `destination_label` / `start_location_label` report columns; the original destination and start-location source values remain unchanged. Examples use fictional labels:

```sh
python bmw_export_journeys.py --report-only ./bmw-capture --replace-label 'Home=Personal base' --replace-label 'Work=Office'
```

Never put personal addresses in command history or shared logs.

## Maintainer-reported phone validation

The maintainer reports successful macOS + Docker validation with an authorized Android phone and the English My BMW journey list. This included doctor, uninterrupted and interrupted/resumed captures, a multi-month capture, and a January–October capture. These results are specific to that tested setup; saved full-year files are not available in this workspace for reinspection. Linux and Windows phone capture remain unverified. CI and launcher tests are offline and do not establish phone or platform networking compatibility.

## Data limits

An app list entry can represent one trip or a grouped set of trips. This exporter preserves grouped counts; it does not split groups or fabricate per-leg distance/duration. The current script does not open groups. Whether this My BMW version exposes individual trips inside a group has not been established from UI evidence. To investigate, enable USB debugging and, with the vehicle list open, capture the group before and after opening it:

```sh
adb devices
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb exec-out cat /sdcard/window.xml > before-group.xml
# Tap one grouped row in the phone UI, wait for it to finish opening, then:
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb exec-out cat /sdcard/window.xml > opened-group.xml
```

Review both files locally and replace or remove VINs, addresses, account identifiers, dates, destinations, and other real journey details before sharing. Keep the two files paired so the UI change can be compared. A real device was available for macOS capture validation, but no before/after XML sample showing group-open behavior was collected. Whether this app version exposes individual trips inside a group remains unverified.

Raw XML preserves what the UI exposed. Distance and date fields are app display values, not independent measurements. The source script does not establish departure/arrival semantics for displayed times.

## Development

Tests use sanitized, fictional XML only:

```sh
python -m unittest discover -s tests -v
python bmw_export_journeys.py --help
```

Contributions should preserve original source values, avoid real journey data in fixtures, and include tests for parsing/report changes. Do not add BMW account authentication or API scraping. See [CONTRIBUTING.md](CONTRIBUTING.md).
