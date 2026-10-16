#!/bin/sh
# Local extraction only, no root, package-manager installation, or security changes.
# Tested on Debian 13 x86_64. Other base systems may lack additional dependencies.
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEST=${1:-"$HERE/perf-local"}
mkdir -p "$DEST/packages" "$DEST/root"
DEST=$(CDPATH= cd -- "$DEST" && pwd)
while read -r digest url; do
    case "$digest" in ''|'#'*) continue;; esac
    name=${url##*/}
    target="$DEST/packages/$name"
    if [ ! -f "$target" ]; then
        curl --fail --location --proto '=https' "$url" --output "$target"
    fi
    printf '%s  %s\n' "$digest" "$target" | sha256sum --check --status
    dpkg-deb --extract "$target" "$DEST/root"
done < "$HERE/perf-packages.sha256-urls"
cat > "$DEST/perf" <<'WRAPPER'
#!/bin/sh
BASE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
export LD_LIBRARY_PATH="$BASE/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PERF_EXEC_PATH="$BASE/root/usr/lib/perf-core"
exec "$BASE/root/usr/bin/perf" "$@"
WRAPPER
chmod +x "$DEST/perf"
"$DEST/perf" --version
printf 'Local perf: %s/perf\n' "$DEST"
