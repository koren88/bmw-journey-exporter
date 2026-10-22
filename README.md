# BMW Journey Exporter

Export the journey history shown in the Android **My BMW** app to an Excel workbook.

The tool drives your own phone over Android Debug Bridge (ADB). It opens no BMW account session of its own, calls no BMW services, and needs no CarData access. It reads the **All journeys** list that the app already displays, scrolls through it month by month, and writes `journeys.xlsx`.

**Unofficial project, not affiliated with or endorsed by BMW.** Treat exports as personal records to review, not as a verified tax or accounting log. Only history still available in the app can be captured.

## What you get

- One workbook, `journeys.xlsx`, with a **Monthly summary** sheet first (completeness status, warnings, BMW totals) followed by one sheet per month in chronological order.
- Optional CSV, JSON and XML files (see [Optional formats](#optional-formats-and-keeping-capture-data)).
- Source values are preserved exactly as the app displays them. Dates are resolved only where the saved capture context supports it (and marked as derived or unresolved otherwise). Details the list does not show, such as start locations, departure and arrival times, and the individual trips inside a group, are left empty and never invented.

**Grouped trips:** the app sometimes shows several trips as one entry (for example "3 trips"). The exporter records that entry and its trip count. It does not open groups, so **the individual trips inside a group are not exported**. The monthly summary compares represented trip counts with BMW's monthly total so you can see whether a month is complete.

## Requirements

**Phone and app (all platforms)**

- An Android phone with the My BMW app, signed in, with the **English** app language. Other languages and layouts are detected as unsupported.
- USB debugging enabled and a USB cable (see [Prepare the phone](#prepare-the-phone)).

**Computer**

| Platform | Needs | Status |
| --- | --- | --- |
| macOS (recommended) | [Docker Desktop](https://www.docker.com/products/docker-desktop/), Android Platform Tools (`adb`), GNU Make, Git | Phone capture tested |
| Linux | Docker, Android Platform Tools, GNU Make, Git | Offline tests only; phone capture unverified |
| Windows | Python 3.9+, Android Platform Tools, Git | Offline tests only; phone capture unverified |

Install Android Platform Tools from [developer.android.com/tools/releases/platform-tools](https://developer.android.com/tools/releases/platform-tools) or a package manager (on macOS: `brew install --cask android-platform-tools`). GNU Make comes with the macOS developer tools; on Linux you may need to install it (for example `sudo apt install make`).

## Get the code

```sh
git clone https://github.com/koren88/bmw-journey-exporter.git
cd bmw-journey-exporter
```

Without Git, use **Code → Download ZIP** on the GitHub page, unzip it, and `cd` into the folder.

## Prepare the phone

Do these steps in order before running `make doctor` or any capture:

1. **Enable Developer options:** *Settings → About phone*, then tap **Build number** seven times. (On some phones it is under *About phone → Software information*.)
2. **Enable USB debugging:** *Settings → System → Developer options → USB debugging* (menu names vary by manufacturer).
3. **Connect the phone by USB**, unlock it, and accept the **Allow USB debugging?** prompt (tick "Always allow from this computer" if offered).
4. **Open My BMW → your vehicle → All journeys**, then select the **latest month you want to export**. Capture moves backward from this month, so open the newest month in your range first.
5. Keep the phone unlocked and leave the app on that screen. Do not touch the phone while a capture is running.

## Recommended path: macOS with Docker and Make

The Make commands run the exporter in a Docker container that talks to the ADB server on your Mac. The first run builds the image, which takes a few minutes. If no ADB server is running, the macOS launcher starts one for you (this does not reset device authorizations).

Check that everything is connected and the phone shows the **All journeys** list:

```sh
make doctor
```

`make doctor` only reads the screen. It never taps, swipes or navigates.

### First successful export

Export one month, keep the phone awake during the run, and save to a folder of your choice:

```sh
make capture MONTH=2026-10 TIMEZONE=Europe/Berlin KEEP_AWAKE=1 OUTPUT=./october-2026
```

- Replace `2026-10` with the latest month you opened in the app, and `Europe/Berlin` with [your own IANA timezone](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). The container otherwise assumes UTC, which can shift capture dates near midnight and month boundaries.
- `KEEP_AWAKE=1` temporarily extends the phone's screen timeout to two hours and restores your original setting when the run ends.
- Other selections: `YEAR=2026` (January through the current month for the current year), or `FROM=2026-09 TO=2026-10` for an inclusive range. Open the **last** month of the range first.
- `OUTPUT` must not exist yet. If you omit it, Make creates `./bmw-export-<timestamp>-<pid>`.

When the run succeeds, your workbook is **`october-2026/journeys.xlsx`** inside the repository folder, and the temporary working data is removed. Exit status `0` means every requested month matched BMW's trip count and the workbook validated. Open the **Monthly summary** sheet first and check each month's status and warnings.

Docker paths must stay inside the repository: `OUTPUT`, `INPUT` and `INPUTS` are resolved relative to it, and paths outside it are rejected. To use a folder elsewhere, the supported alternative is the [local Python CLI](#advanced-usage); manually configured Docker mounts are possible but not provided or tested by the launchers.

## If a capture is interrupted

Working data is saved as the run progresses, under `<OUTPUT>/capture-data/`. If the run stops (Ctrl+C, locked phone, unplugged cable, screen change, a month whose count does not match BMW, or a report failure), that data is **kept automatically** and the tool prints the commands to continue. You do not need any option for this.

To continue: reconnect and unlock the phone, reopen **All journeys** on the same latest month you started with, then run:

```sh
make resume OUTPUT=./october-2026
```

Resume loads the saved month selection and settings (including `KEEP_AWAKE`). Settings you pass that disagree with the saved ones are rejected. If resume cannot match the screen against the saved rows (for example because repeated identical entries make a boundary ambiguous), it stops without changing saved data.

A month is **complete** only when the represented trip count equals BMW's monthly total and the bottom of the list was reached. Statuses in the summary: `complete`, `incomplete` (mismatch or interrupted), `failed` (nothing usable captured) and `pending` (not attempted). Exit status `2` means the capture finished but is incomplete.

## Optional formats and keeping capture data

By default, a successful capture leaves only `journeys.xlsx`. To also write other formats at capture time:

```sh
make capture MONTH=2026-10 TIMEZONE=Europe/Berlin KEEP_AWAKE=1 OUTPUT=./october-2026 FORMATS=xlsx,csv
```

`FORMATS` accepts `xlsx`, a comma-separated list from `xlsx,csv,json,xml`, or `all`.

Recovery data after an *interrupted* run is automatic. A separate option, **`KEEP_CAPTURE=1`**, keeps the working data after a *successful* run so you can later regenerate reports or merge captures. Without it, successful runs delete that data and cannot be turned into other formats afterwards.

```sh
# Capture and keep the data for later
make capture MONTH=2026-10 TIMEZONE=Europe/Berlin KEEP_AWAKE=1 OUTPUT=./october-2026 KEEP_CAPTURE=1

# Later, offline (no phone needed): write more formats from the retained data
make report INPUT=./october-2026 FORMATS=xlsx,csv,json

# Merge retained captures from different runs into a new folder.
# ./september-2026 must be a separate capture (e.g. MONTH=2026-09 OUTPUT=./september-2026)
# that was also made with KEEP_CAPTURE=1; captures without retained data cannot be merged.
make merge INPUTS='./september-2026:./october-2026' OUTPUT=./merged-2026
```

- `KEEP_DEBUG=1` also keeps the raw screen XML (it implies `KEEP_CAPTURE=1`). The XML contains whatever the app displayed, such as addresses, so treat it as private.
- `make report` writes the selected files into the capture folder and leaves other report files from earlier runs in place.
- `make merge`: `INPUTS` is a colon-separated list (a colon inside a path is not supported) and `OUTPUT` must be new. Sources must be captures whose data was retained. Overlaps are only merged when the sequence alignment is provable; conflicting values stop the merge unless you set `CONFLICT=keep-first` or `CONFLICT=keep-last`. A merged month is `complete` only if at least one source was individually complete and the merged counts still match BMW's total. Merged data can be reported and merged again but cannot resume a phone capture.

## Reading the output

XLSX month sheets contain these columns, in order: `month`, `list_sequence`, `week_context`, `destination`, `destination_label`, `displayed_date_time`, `resolved_date`, `date_basis`, `distance_km_numeric`, `distance_km_source`, `duration_numeric`, `duration_displayed`, `consumption_displayed`, `grouped_trip_count`, `start_location`, `departure_time`, `arrival_time`.

- Grouped entries are highlighted and carry their trip count in `grouped_trip_count`.
- Distances shown by the app are rounded. BMW's monthly distance and the sum of the displayed entry distances are shown separately in the summary because they can differ.
- `displayed_date_time` is kept verbatim. `resolved_date` is filled only when the displayed text and the saved capture date agree (for example "Wednesday" under a known week). `date_basis` says how the date was derived or why it stayed unresolved.
- `start_location`, `departure_time` and `arrival_time` exist as columns but are left empty, because the list does not show them.
- CSV, JSON and XML additionally contain technical fields (raw text, source XML name, capture date, provenance and merge conflicts). Source text is preserved exactly, so spreadsheet software may treat CSV cells starting with `=`, `+`, `-` or `@` as formulas; prefer the XLSX file for opening in Excel, which stores source strings as literal text.

## Windows and Linux

Phone capture on Linux and Windows has **not** been verified on real hardware. The offline test suite runs in CI on macOS, Linux and Windows, but those tests use no phone, USB authorization or Docker-to-host ADB networking. Expect to troubleshoot.

**Windows (native Python, PowerShell).** GNU Make and the Docker launchers are not used. Install Python 3.9+ and Android Platform Tools, then from the repository folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
adb start-server
adb devices            # the phone should be listed as "device", not "unauthorized"
# Prepare the phone as described above (All journeys, latest month open), then:
python bmw_export_journeys.py --doctor
python bmw_export_journeys.py --month 2026-10 --keep-awake --output '.\october-2026'
python bmw_export_journeys.py --resume --output '.\october-2026'
```

The workbook appears at `october-2026\journeys.xlsx`. WSL does not automatically get access to a USB phone; set that up yourself before trying any Linux instructions inside it.

**Linux (Docker and Make).** The Linux launcher does not start or reconfigure ADB, and it runs the container with host networking. Start the ADB server yourself, then tell the launcher which address the container should use to reach it:

```sh
adb start-server
export BMW_ADB_HOST=127.0.0.1     # host/IP where the existing ADB server listens
export BMW_ADB_PORT=5037          # optional; 5037 is the default
make doctor
make capture MONTH=2026-10 TIMEZONE=Europe/Berlin KEEP_AWAKE=1 OUTPUT=./october-2026
```

`BMW_ADB_HOST` is required for every Linux phone command (`make doctor`, `capture`, `resume`); `make report` and `make merge` do not need it. Do not expose the ADB server to an untrusted network. Launcher containers run as your user ID so output files are not owned by root; this has offline argument tests only.

Alternatively, run the Python CLI directly on Linux or macOS with `make setup` followed by `./.venv/bin/python bmw_export_journeys.py ...`.

## Advanced usage

**Local Python CLI** (any platform; the supported way to use capture folders outside the repository):

```sh
python3 -m venv .venv
. .venv/bin/activate               # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
adb start-server                   # the CLI never starts or restarts ADB itself
python bmw_export_journeys.py --doctor
python bmw_export_journeys.py --from-month 2026-09 --to-month 2026-10 --keep-capture --output ./sep-oct-2026

# Later, offline: needs the data retained by --keep-capture
python bmw_export_journeys.py --report-only ./sep-oct-2026 --formats all
python bmw_export_journeys.py --merge ./sep-oct-2026 --merge ./other-capture --output ./merged   # ./other-capture also made with --keep-capture

# Alternative, only after an interrupted or incomplete capture (recovery data is kept automatically)
python bmw_export_journeys.py --resume --output ./sep-oct-2026
```

Run `python bmw_export_journeys.py --help` for all options. Useful ones: `--serial` (required when several authorized devices are connected), `--timezone`, `--pause SECONDS` (minimum 0.5), `--max-pages`, `--keep-capture`, `--keep-debug`, `--keep-awake`, `--conflict {error,keep-first,keep-last}`.

**Label substitution.** `--replace-label OLD=NEW` (repeatable) replaces whole-value matches in the added `destination_label` column (XLSX, CSV, JSON, XML) and `start_location_label` (CSV, JSON, XML only; the XLSX `start_location` column always shows the source value). Original `destination` and `start_location` values are never changed. It is available on the Python CLI with capture, `--report-only` and `--merge`, not through Make:

```sh
python bmw_export_journeys.py --report-only ./october-2026 --replace-label 'Home=Personal base'
```

**Exit statuses.** `0`: complete and reports validated. `1`: runtime, preflight or report validation error. `2`: incomplete capture or merge, or an invalid command line. Make may report its own failure status instead of the underlying one.

**Screen timeout.** With `--keep-awake`, the original timeout is saved locally before it is changed and restored on normal exit, Ctrl+C and SIGTERM. If restoration fails, the tool prints an `adb -s SERIAL shell settings put system screen_off_timeout VALUE` command to restore it manually. Restoration cannot be guaranteed after a hard kill or a lost connection; a later resume checks for an unresolved record first and refuses to guess if the device or value does not match.

**Phone-side files.** Each UI dump is a temporary XML file on the phone (`/sdcard/bmw-export-*.xml`, or `/sdcard/bmw-doctor-*.xml` for doctor). The tool removes only its own exact file when it exits and warns if that fails.

**Data on disk.** New captures keep working data in `<output>/capture-data/` (checkpoints, a source CSV, `checks.json` status record, and raw XML in `raw/` while active). Legacy capture folders with files at their root still work. Cleanup removes only files created by the capture; existing user folders are never migrated or cleaned automatically. Everything under `capture-data/` and all report files are covered by `.gitignore`.

**Exploring group contents.** Whether this app version exposes individual trips inside a group has not been established, and no sample has been collected. If you want to investigate, save the UI before and after opening one grouped row, remove VINs, addresses and other personal details before sharing, and open an issue:

```sh
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb exec-out cat /sdcard/window.xml > before-group.xml
# Open one grouped row on the phone, wait for it to finish, then:
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb exec-out cat /sdcard/window.xml > opened-group.xml
```

**Docker without the launchers** (Windows Docker Desktop; unverified): `docker run --rm -v "${PWD}/bmw-capture:/capture" -e ADB_SERVER_SOCKET=tcp:host.docker.internal:5037 bmw-journey-exporter --month 2026-10 --output /capture/run` after `docker build -t bmw-journey-exporter .`.

## Tested versus unverified

| Environment | Offline tests (CI) | Phone capture |
| --- | --- | --- |
| macOS + Docker + Make | Run in CI | Verified by the maintainer with an authorized phone: doctor, single month, interrupted and resumed capture, multi-month capture |
| Linux + Docker + Make | Run in CI, using a fake Docker | **Unverified** |
| Windows native Python | Run in CI | **Unverified** |
| WSL | Not covered | **Unverified** |

The phone results apply only to the maintainer's phone, app version and English UI. Offline tests do not establish compatibility with other phones, app versions, USB authorization, or Docker-to-host ADB networking. The local Python CLI is documented for Python 3.9 or newer, but CI exercises only 3.12.

## Development

Tests use sanitized, fictional XML only and need no phone:

```sh
make test                                 # or: python -m unittest discover -s tests -v
python bmw_export_journeys.py --help
```

`make test` prefers `.venv/bin/python`, then `python3`, and falls back to Docker if project dependencies are missing; set `PYTHON=/path/to/python` to choose an interpreter. Contributions should preserve original source values, avoid real journey data in fixtures, and include tests for parser, merge, date, report and launcher changes. Do not add BMW account authentication or private API calls. See [CONTRIBUTING.md](CONTRIBUTING.md).

For community reports, see the [bug report form](https://github.com/koren88/bmw-journey-exporter/issues/new?template=bug_report.yml), [feature request form](https://github.com/koren88/bmw-journey-exporter/issues/new?template=feature_request.yml), [accessibility notes](ACCESSIBILITY.md), and [security policy](SECURITY.md).
