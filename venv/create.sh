#!/bin/bash
# setup virtnbdbackup within virtualenv including
# required libnbd bindings.
VENVDIR=$(pwd)/virtnbdbackup-venv
LIBNBD_MAJ="1.22-stable"
LIBNBD_VERSION="libnbd-1.22.5"

set -e

BRANCH="master"
if [ -n "$1" ]; then
    BRANCH="$1"
fi
rm -rf virtnbdbackup
rm -rf "${VENVDIR}"
rm -rf "${LIBNBD_VERSION}"
rm -rf libnbd-*

virtualenv -p "$(which python3)" "${VENVDIR}"
git clone https://github.com/abbbi/virtnbdbackup.git -b "${BRANCH}"
# shellcheck source=/dev/null
source "${VENVDIR}/bin/activate"
pip install -U setuptools
curl https://download.libguestfs.org/libnbd/${LIBNBD_MAJ}/${LIBNBD_VERSION}.tar.gz  > ${LIBNBD_VERSION}.tar.gz
tar xzf ${LIBNBD_VERSION}.tar.gz
cd ${LIBNBD_VERSION}
export bashcompdir=/tmp
./configure --prefix="${VENVDIR}" --exec-prefix="${VENVDIR}" \
    --disable-ocaml \
    --disable-golang \
    --disable-fuse
make -j "$(nproc)"
make install
cd ..
python -m pip install -r virtnbdbackup/requirements.txt 
cd virtnbdbackup/
pip install -U .
