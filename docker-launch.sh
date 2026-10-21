#!/bin/sh
# Shared image build, offline/test execution, and platform-specific ADB forwarding.
set -eu
project_dir=$(CDPATH= cd -P -- "$(dirname -- "$0")" && pwd -P)
cd "$project_dir"
mode=${1:-}
[ -n "$mode" ] || { echo 'Internal launcher mode is required.' >&2; exit 2; }
shift
command -v docker >/dev/null 2>&1 || { echo 'Docker was not found.' >&2; exit 2; }

if [ "$mode" != test ]; then
  case "$mode" in
    macos) [ "$(uname -s)" = Darwin ] || { echo 'The macOS launcher must run on macOS.' >&2; exit 2; } ;;
    linux) [ "$(uname -s)" = Linux ] || { echo 'The Linux launcher must run on Linux.' >&2; exit 2; } ;;
    *) echo "Unsupported launcher mode: $mode" >&2; exit 2 ;;
  esac
fi

if [ "$mode" != test ]; then
  # The only writable host mount is the project root. Resolve existing
  # directories through symlinks and normalize non-existing output suffixes.
  path_to_container() {
    requested=$1
    required=$2
    case "$requested" in /*) candidate=$requested ;; *) candidate=$project_dir/$requested ;; esac
    while [ "$candidate" != / ] && [ "${candidate%/}" != "$candidate" ]; do candidate=${candidate%/}; done
    if [ -d "$candidate" ]; then
      resolved=$(CDPATH= cd -P -- "$candidate" 2>/dev/null && pwd -P) || {
        echo "Cannot resolve path: $requested" >&2; return 2;
      }
    else
      if [ -e "$candidate" ]; then
        echo "Expected a directory path, but found a non-directory: $requested" >&2; return 2
      fi
      suffix=
      probe=$candidate
      while [ ! -d "$probe" ]; do
        if [ -L "$probe" ]; then
          echo "Cannot safely resolve a dangling symlink in Docker path: $requested ($probe)" >&2
          echo 'Replace it with a real directory path, or use the local Python CLI for external paths.' >&2
          return 2
        fi
        component=${probe##*/}
        [ -n "$component" ] || { echo "Cannot resolve path: $requested" >&2; return 2; }
        suffix=/$component$suffix
        parent=${probe%/*}
        [ -n "$parent" ] || parent=/
        [ "$parent" != "$probe" ] || parent=/
        probe=$parent
      done
      resolved=$(CDPATH= cd -P -- "$probe" 2>/dev/null && pwd -P) || {
        echo "Cannot resolve path: $requested" >&2; return 2;
      }
      rest=${suffix#/}
      while [ -n "$rest" ]; do
        component=${rest%%/*}
        if [ "$rest" = "$component" ]; then rest=; else rest=${rest#*/}; fi
        case "$component" in
          ''|.) ;;
          ..) [ "$resolved" = / ] || resolved=${resolved%/*}; [ -n "$resolved" ] || resolved=/ ;;
          *) resolved=${resolved%/}/$component ;;
        esac
      done
    fi
    if [ "$required" = yes ] && [ ! -d "$resolved" ]; then
      echo "Directory does not exist: $requested" >&2; return 2
    fi
    case "$resolved" in
      "$project_dir") printf '%s\n' /workspace ;;
      "$project_dir"/*) printf '/workspace/%s\n' "${resolved#"$project_dir"/}" ;;
      *)
        echo "Docker path is outside the mounted repository: $requested resolves to $resolved" >&2
        echo 'Use a path inside the repository (mounted at /workspace), or use the local Python CLI for external capture/report paths.' >&2
        return 2 ;;
    esac
  }

  args_file=$(mktemp "${TMPDIR:-/tmp}/bmw-docker-args.XXXXXX")
  trap 'rm -f "$args_file"' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  for arg do printf '%s\n' "$arg"; done > "$args_file"
  set --
  path_option=
  host_output_path=
  host_report_path=
  while IFS= read -r arg || [ -n "$arg" ]; do
    if [ -n "$path_option" ]; then
      required=no; [ "$path_option" = --output ] || required=yes
      if [ "$path_option" = --output ]; then host_output_path=$arg; host_report_path=$arg; fi
      [ "$path_option" != --report-only ] || host_report_path=$arg
      mapped=$(path_to_container "$arg" "$required") || exit $?
      set -- "$@" "$path_option" "$mapped"
      path_option=
      continue
    fi
    case "$arg" in
      --output|--report-only|--merge) path_option=$arg ;;
      --output=*|--report-only=*|--merge=*)
        option=${arg%%=*}; value=${arg#*=}
        if [ "$option" = --output ]; then host_output_path=$value; host_report_path=$value; fi
        [ "$option" != --report-only ] || host_report_path=$value
        required=no; [ "$option" = --output ] || required=yes
        mapped=$(path_to_container "$value" "$required") || exit $?
        set -- "$@" "$option=$mapped" ;;
      --out|--out=*)
        echo "Unsupported abbreviated path option: $arg. Use --output PATH (or --output=PATH)." >&2
        exit 2 ;;
      *) set -- "$@" "$arg" ;;
    esac
  done < "$args_file"
  rm -f "$args_file"
  trap - EXIT HUP INT TERM
fi

# Keep the user's host path available to recovery instructions after CLI paths
# have been translated into the container's /workspace mount.
docker_env_args=
if [ -n "${host_output_path:-}" ]; then
  export BMW_HOST_OUTPUT_PATH=$host_output_path
  docker_env_args="$docker_env_args -e BMW_HOST_OUTPUT_PATH"
fi
if [ -n "${host_report_path:-}" ]; then
  export BMW_HOST_REPORT_PATH=$host_report_path
  docker_env_args="$docker_env_args -e BMW_HOST_REPORT_PATH"
fi
if [ -n "${host_output_path:-}${host_report_path:-}" ]; then
  export BMW_HOST_PATHS_FROM_LAUNCHER=1
  docker_env_args="$docker_env_args -e BMW_HOST_PATHS_FROM_LAUNCHER"
fi

if command -v sha256sum >/dev/null 2>&1; then
  source_hash=$(sha256sum bmw_export_journeys.py Dockerfile requirements.txt | sha256sum | awk '{print $1}')
else
  source_hash=$(shasum -a 256 bmw_export_journeys.py Dockerfile requirements.txt | shasum -a 256 | awk '{print $1}')
fi
image_hash=$(docker image inspect --format '{{ index .Config.Labels "org.bmwjourney.source" }}' bmw-journey-exporter 2>/dev/null || true)
if [ "$image_hash" != "$source_hash" ]; then
  echo 'Building or refreshing bmw-journey-exporter image.'
  docker build --build-arg PROJECT_HASH="$source_hash" -t bmw-journey-exporter .
fi

if [ "$mode" = test ]; then
  exec docker run --rm --user "$(id -u):$(id -g)" -v "$project_dir:/workspace" -w /workspace --entrypoint python bmw-journey-exporter -m unittest discover -s tests -v
fi

needs_adb=1
for arg in "$@"; do
  case "$arg" in --help|-h|--report-only|--report-only=*|--merge|--merge=*) needs_adb=0 ;; esac
done
if [ "$needs_adb" -eq 1 ]; then
  if [ "$mode" = macos ]; then
    command -v adb >/dev/null 2>&1 || { echo 'Install Android Platform Tools and put adb on PATH.' >&2; exit 2; }
    command -v nc >/dev/null 2>&1 || { echo 'The macOS launcher needs nc to check the host ADB socket.' >&2; exit 2; }
    if ! nc -z -w 1 127.0.0.1 5037 >/dev/null 2>&1; then
      echo 'No host ADB server is listening on 127.0.0.1:5037.'
      echo 'Starting ADB because the macOS Docker path uses the host server. This does not reset device authorizations.'
      adb start-server
    fi
    if ! nc -z -w 1 127.0.0.1 5037 >/dev/null 2>&1; then echo 'Host ADB server is still unreachable.' >&2; exit 1; fi
    ADB_SERVER_SOCKET=tcp:127.0.0.1:5037 adb devices
    adb_host=host.docker.internal
    adb_port=5037
    docker_network_args=
  else
    [ -n "${BMW_ADB_HOST:-}" ] || { echo 'Set BMW_ADB_HOST to the host address reachable from the Linux container (for example 127.0.0.1 with host networking).' >&2; exit 2; }
    adb_host=$BMW_ADB_HOST
    adb_port=${BMW_ADB_PORT:-5037}
    case "$adb_port" in *[!0-9]*|'') echo 'BMW_ADB_PORT must be a numeric TCP port.' >&2; exit 2 ;; esac
    [ "$adb_port" -ge 1 ] && [ "$adb_port" -le 65535 ] || { echo 'BMW_ADB_PORT must be between 1 and 65535.' >&2; exit 2; }
    docker_network_args=--network
    docker_network_mode=host
  fi
  adb_socket="tcp:${adb_host}:${adb_port}"
  if [ "$mode" = macos ]; then
    if ! docker run --rm --entrypoint python -e "ADB_SERVER_SOCKET=$adb_socket" bmw-journey-exporter -c "import socket; s=socket.create_connection(('$adb_host',$adb_port),timeout=3); s.sendall(b'000chost:version'); f=s.makefile('rb'); status=f.read(4); n=int(f.read(4),16) if status==b'OKAY' else 0; payload=f.read(n) if n else b''; print('ADB server protocol:',payload.decode(errors='replace')); f.close(); s.close(); assert status==b'OKAY'"; then
      echo 'Docker cannot reach host.docker.internal:5037; no capture was started.' >&2; exit 1
    fi
  else
    if ! docker run --rm --network host --entrypoint python -e "ADB_SERVER_SOCKET=$adb_socket" bmw-journey-exporter -c "import socket; s=socket.create_connection(('$adb_host',$adb_port),timeout=3); s.sendall(b'000chost:version'); f=s.makefile('rb'); status=f.read(4); n=int(f.read(4),16) if status==b'OKAY' else 0; payload=f.read(n) if n else b''; print('ADB server protocol:',payload.decode(errors='replace')); f.close(); s.close(); assert status==b'OKAY'"; then
      echo "Container cannot reach explicitly configured ADB server $adb_host:$adb_port; no capture was started." >&2
      echo 'On Linux, host ADB networking must already be reachable. This launcher does not start or reconfigure ADB.' >&2
      exit 1
    fi
  fi
fi

if [ "$needs_adb" -eq 1 ]; then
  if [ "$mode" = macos ]; then
    exec docker run --rm -it $docker_env_args -v "$project_dir:/workspace" -w /workspace -e "ADB_SERVER_SOCKET=$adb_socket" bmw-journey-exporter "$@"
  else
    exec docker run --rm -it --user "$(id -u):$(id -g)" $docker_env_args "$docker_network_args" "$docker_network_mode" -v "$project_dir:/workspace" -w /workspace -e "ADB_SERVER_SOCKET=$adb_socket" bmw-journey-exporter "$@"
  fi
else
  if [ "$mode" = linux ]; then
    exec docker run --rm --user "$(id -u):$(id -g)" $docker_env_args -v "$project_dir:/workspace" -w /workspace bmw-journey-exporter "$@"
  else
    exec docker run --rm $docker_env_args -v "$project_dir:/workspace" -w /workspace bmw-journey-exporter "$@"
  fi
fi
