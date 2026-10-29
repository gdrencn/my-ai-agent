#!/bin/sh
# Generated from scripts/entry.template.sh and the shared dependency command table.
set -eu
maa_python=''
maa_find_python() {
    for maa_candidate in python3 python3.14 python3.13 python3.12 python3.11; do
        if command -v "$maa_candidate" >/dev/null 2>&1 && "$maa_candidate" -c 'import sys;raise SystemExit(sys.version_info < (3,11))' 2>/dev/null; then
            maa_python=$maa_candidate
            return 0
        fi
    done
    return 1
}
maa_packages=''
command -v curl >/dev/null 2>&1 || maa_packages='curl ca-certificates'
maa_find_python || maa_packages="$maa_packages python3"
if [ -n "$maa_packages" ]; then
    maa_privilege=''
    if [ "$(id -u)" != 0 ]; then
        command -v sudo >/dev/null 2>&1 || { echo 'Install prerequisites as root, or provide sudo.' >&2; exit 1; }
        maa_privilege=sudo
    fi
    maa_prepared=0
    if [ "$maa_prepared" = 0 ] && command -v apt-get >/dev/null 2>&1; then
        maa_native_packages=''
        for maa_package in $maa_packages; do
            maa_native_packages="$maa_native_packages $maa_package"
        done
        $maa_privilege apt-get update
        $maa_privilege apt-get install -y $maa_native_packages
        maa_prepared=1
    fi
    if [ "$maa_prepared" = 0 ] && command -v dnf >/dev/null 2>&1; then
        maa_native_packages=''
        for maa_package in $maa_packages; do
            maa_native_packages="$maa_native_packages $maa_package"
        done
        $maa_privilege dnf install -y $maa_native_packages
        maa_prepared=1
    fi
    if [ "$maa_prepared" = 0 ] && command -v yum >/dev/null 2>&1; then
        maa_native_packages=''
        for maa_package in $maa_packages; do
            maa_native_packages="$maa_native_packages $maa_package"
        done
        $maa_privilege yum install -y $maa_native_packages
        maa_prepared=1
    fi
    if [ "$maa_prepared" = 0 ] && command -v zypper >/dev/null 2>&1; then
        maa_native_packages=''
        for maa_package in $maa_packages; do
            maa_native_packages="$maa_native_packages $maa_package"
        done
        $maa_privilege zypper --non-interactive install $maa_native_packages
        maa_prepared=1
    fi
    if [ "$maa_prepared" = 0 ] && command -v pacman >/dev/null 2>&1; then
        maa_native_packages=''
        for maa_package in $maa_packages; do
            [ "$maa_package" != python3 ] || maa_package=python
            maa_native_packages="$maa_native_packages $maa_package"
        done
        $maa_privilege pacman -S --needed --noconfirm $maa_native_packages
        maa_prepared=1
    fi
    [ "$maa_prepared" = 1 ] || { echo "Install these prerequisites with your package manager: $maa_packages" >&2; exit 1; }
fi
maa_find_python || { echo 'Python 3.11+ is required; install a supported Python version.' >&2; exit 1; }
maa_tmp=$(mktemp -d)
trap 'rm -rf "$maa_tmp"' EXIT HUP INT TERM
curl -fsSL https://raw.githubusercontent.com/gdrencn/my-ai-agent/main/bootstrap.py -o "$maa_tmp/bootstrap.py"
"$maa_python" "$maa_tmp/bootstrap.py" --channel test --version 0.1.14 --test "$@"
