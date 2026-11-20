#!/usr/bin/env bash
# Builds the console's two files with Docker, the macOS and Linux twin of
# BuildConsole.bat (docs/DEVELOPMENT.md, section 4), and puts them in this
# folder's "SD card/DSiRPC", where DSiRPC run from here offers them to the
# launcher as an update. Docker Desktop (or the Docker engine) has to be
# running. Both images have arm64 builds, so Apple Silicon runs them natively.
#
#   ./build.sh                  builds both files
#   ./build.sh ~/path/DSiRPC    also copies them into that DSiRPC folder
#                               (a download you run DSiRPC from)

set -euo pipefail
cd "$(dirname "$0")"

failed() {
	echo
	echo "It didn't work (is Docker running?). The messages above say more."
	exit 1
}
trap failed ERR

if ! docker info >/dev/null 2>&1; then
	echo "Docker isn't running: start Docker Desktop and try again."
	exit 1
fi

echo "Building the launcher..."
docker run --rm -v "$PWD/launcher:/work" -w /work --entrypoint make skylyrac/blocksds:slim-latest

echo
echo "Building nds-bootstrap (a few minutes)..."
# The version its in-game menu shows. nds-bootstrap's arm9/Makefile asks git,
# but git can't see this repo from inside Docker (only nds-bootstrap/ is
# mounted), so it's worked out here the same way: the tag if this commit has
# one, else the last tag and the commit.
GIT_VER=$(git describe --tags --abbrev=0 2>/dev/null || echo dev)
if ! git describe --tags --exact-match >/dev/null 2>&1; then
	GIT_VER="$GIT_VER-$(git rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"
fi
echo "Version: $GIT_VER"
docker run --rm -v "$PWD/nds-bootstrap:/build" -w /build devkitpro/devkitarm:20241104 bash -c "sed -i '/security/d' /etc/apt/sources.list && apt-get update && apt-get install -y gcc && gcc lzss.c -o /usr/local/bin/lzss && make nightly GIT_VER=$GIT_VER"

copy_to() {
	mkdir -p "$1/SD card/DSiRPC"
	cp "launcher/dsirpc-launcher.nds" "$1/SD card/DSiRPC/dsirpc-launcher.nds"
	cp "nds-bootstrap/retail/bin/nds-bootstrap-nightly.nds" "$1/SD card/DSiRPC/nds-bootstrap-dsirpc.nds"
	echo "Copied both files to \"$1/SD card/DSiRPC\""
}
copy_to "$PWD"
if [ $# -gt 0 ] && [ -n "$1" ]; then
	copy_to "$1"
fi

echo
echo "Done. Start the launcher while DSiRPC runs and it offers the new files."
