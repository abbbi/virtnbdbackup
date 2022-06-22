#!/bin/bash
set -e
rm -rf virtnbdbackup
virtualenv -p $(which python3) virtnbdbackup 
cd virtnbdbackup 
git clone https://github.com/abbbi/virtnbdbackup.git 
source bin/activate 
wget -U blah https://download.libguestfs.org/libnbd/1.12-stable/libnbd-1.12.4.tar.gz && tar xzf libnbd-1.12.4.tar.gz 
python -m pip install ocaml 
cd libnbd-1.12.4 
./configure --prefix=$(pwd)/../virtnbdbackup/ --exec-prefix=$(pwd)/../virtnbdbackup/ 
make -j $(nproc) && make install DESTDIR=$(pwd)/../virtnbdbackup/ && cd .. 
python -m pip install -r virtnbdbackup/requirements.txt 
cd virtnbdbackup/
python setup.py install
