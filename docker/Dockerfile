# based on Docker image created by
# Adrián Parilli <adrian.parilli@staffwerke.de>
# Uses parent directory as context:
# git clone https://github.com/abbbi/virtnbdbackup
# cd virtnbdbackup
# docker build -f docker/Dockerfile .
FROM debian:bookworm-slim

ARG DEBIAN_FRONTEND="noninteractive"
ARG source="https://github.com/abbbi/virtnbdbackup"

LABEL container.name="virtnbdbackup-docker"
LABEL container.source.description="Backup utiliy for Libvirt kvm / qemu with Incremental backup support via NBD"
LABEL container.description="virtnbdbackup and virtnbdrestore (plus dependencies) to run on hosts with libvirt >= 6.0.0"
LABEL container.source=$source
LABEL container.version="1.1"
LABEL maintainer="Michael Ablassmeier <abi@grinser.de>"

COPY . /tmp/build/

# Deploys dependencies and pulls sources, installing virtnbdbackup and removing unnecessary content:
RUN \
apt-get update && \
apt-get install -y --no-install-recommends \
ca-certificates openssh-client python3-all python3-libnbd python3-libvirt python3-lz4 python3-setuptools python3-tqdm qemu-utils python3-lxml python3-paramiko python3-colorlog && \
cd /tmp/build/ && python3 setup.py install && cd .. && \
apt-get purge -y ca-certificates && apt-get -y autoremove --purge && apt-get clean && \
rm -rf /var/lib/apt/lists/* /tmp/*

# Default folder:
WORKDIR /
