#!/bin/bash
# setup virtnbdbackup within virtualenv including
# required libnbd bindings.
VENVDIR=$(pwd)/virtnbdbackup-venv
LIBNBD_MAJ="1.12-stable"
LIBNBD_VERSION="libnbd-1.12.4.tar.gz"

set -e
rm -rf virtnbdbackup
rm -rf ${VENVDIR}
rm -f ${LIBNBD_VERSION}
rm -rf libnbd-*

virtualenv -p $(which python3) ${VENVDIR}
git clone https://github.com/abbbi/virtnbdbackup.git 
source ${VENVDIR}/bin/activate
curl https://download.libguestfs.org/libnbd/${LIBNBD_MAJ}/${LIBNBD_VERSION}  > ${LIBNBD_VERSION}
tar xzf ${LIBNBD_VERSION}
cd libnbd-1.12.4 
export bashcompdir=/tmp
./configure --prefix=${VENVDIR} --exec-prefix=${VENVDIR} \
    --disable-ocaml \
    --disable-golang \
    --disable-fuse
make -j $(nproc)
make install
cd ..
python -m pip install -r virtnbdbackup/requirements.txt 
cd virtnbdbackup/
python setup.py install
