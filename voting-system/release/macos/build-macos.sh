#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != Darwin ]]; then
    printf '%s\n' 'Build this bundle on a macOS runner.' >&2
    exit 1
fi

source_dir=$(cd "${1:?Usage: build-macos.sh SOURCE_DIR OUTPUT_DIR}" && pwd)
output_dir=${2:?Usage: build-macos.sh SOURCE_DIR OUTPUT_DIR}
script_dir=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
arch=${VOTELAB_MACOS_ARCH:-$(uname -m)}
case "$arch" in
    arm64) chip=Apple-Silicon ;;
    x86_64) chip=Intel ;;
    *) printf 'Unsupported macOS architecture: %s\n' "$arch" >&2; exit 1 ;;
esac

if [[ "$(uname -m)" != "$arch" ]]; then
    printf 'Runner architecture does not match %s.\n' "$arch" >&2
    exit 1
fi

work_dir=$(mktemp -d "${TMPDIR:-/tmp}/votelab-mac.XXXXXXXX")
server_pid=''
stop_server() {
    if [[ -n "$server_pid" ]]; then
        kill "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
        server_pid=''
    fi
}
cleanup() {
    stop_server
    rm -rf -- "$work_dir"
}
trap cleanup EXIT

python -m venv "$work_dir/venv"
py="$work_dir/venv/bin/python"
"$py" -m pip install --disable-pip-version-check -r "$source_dir/requirements.txt" 'PyInstaller==6.22.3'
"$py" -c 'import platform, sys; sys.exit(platform.machine() != sys.argv[1])' "$arch"

(
    cd "$source_dir"
    "$py" -m unittest discover -v
)

mkdir -p "$work_dir/spec"
"$py" -m PyInstaller --noconfirm --clean --onedir --windowed --noupx \
    --name VoteLab --osx-bundle-identifier org.com3500.votelab \
    --target-arch "$arch" --specpath "$work_dir/spec" \
    --distpath "$work_dir/dist" --workpath "$work_dir/build" \
    --add-data "$source_dir/schema.sql:." --add-data "$source_dir/static:static" \
    "$source_dir/run_votelab.py"

package_name="VoteLab-macOS-$chip"
package_dir="$work_dir/$package_name"
archive="$work_dir/$package_name.zip"
mkdir -p "$package_dir"
ditto "$work_dir/dist/VoteLab.app" "$package_dir/VoteLab.app"
cp "$script_dir/先读我.txt" "$package_dir/先读我.txt"
if [[ -f "$source_dir/release/READ ME FIRST.txt" ]]; then
    cp "$source_dir/release/READ ME FIRST.txt" "$package_dir/READ ME FIRST.txt"
fi
ditto -c -k --sequesterRsrc --keepParent "$package_dir" "$archive"

# Smoke-test the actual distributable ZIP from a working directory without any source files.
mkdir -p "$work_dir/unpacked" "$work_dir/empty" "$work_dir/data"
ditto -x -k "$archive" "$work_dir/unpacked"
app_dir="$work_dir/unpacked/$package_name/VoteLab.app"
binary="$app_dir/Contents/MacOS/VoteLab"
test -x "$binary"
test "$(lipo -archs "$binary")" = "$arch"
codesign --verify --deep --strict --verbose=2 "$app_dir"

cd "$work_dir/empty"
start_server() {
    local log_path="$work_dir/server-$1.log"
    port=$("$py" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')
    base_url="http://127.0.0.1:$port"
    VOTELAB_DATA_DIR="$work_dir/data" "$binary" --no-browser --port "$port" > "$log_path" 2>&1 &
    server_pid=$!
    for _ in {1..30}; do
        if curl --fail --silent --max-time 2 "$base_url/" > "$work_dir/home.html" && \
            grep -q 'VoteLab' "$work_dir/home.html"; then
            return 0
        fi
        if ! kill -0 "$server_pid" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    printf '%s\n' 'The packaged app did not serve the VoteLab home page.' >&2
    cat "$log_path" >&2
    cat "$work_dir/data/launcher.log" >&2 2>/dev/null || true
    return 1
}

start_server before
curl --fail --silent --max-time 5 "$base_url/static/style.css" > "$work_dir/site.css"
test -s "$work_dir/site.css"
"$py" - "$work_dir/data/voting.sqlite3" <<'PY'
import pathlib
import sqlite3
import sys

database = pathlib.Path(sys.argv[1])
with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
    tables = {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
if not {"elections", "ballots"}.issubset(tables):
    raise SystemExit(f"Packaged app did not initialise its database schema: {tables}")
PY

persistence_test="$source_dir/tools/http_persistence_smoke.py"
"$py" "$persistence_test" before "$base_url" "$work_dir/fixture.json"
stop_server
start_server after
"$py" "$persistence_test" after "$base_url" "$work_dir/fixture.json"
compgen -G "$work_dir/data/backups/voting-*.sqlite3" > /dev/null
stop_server

cp "$archive" "$output_dir/$package_name.zip"
shasum -a 256 "$output_dir/$package_name.zip"
