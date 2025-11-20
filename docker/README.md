## Overview

This dockerfile is intended for scenarios where isn't viable to provide the
necessary environment, such as dependencies or tools, due to system
limitations; such as an old OS version, immutable or embedded rootfs, live
distros, docker oriented OSes, etc.

Originally was created to be used on Unraid OS (tested since v6.9.2), and
should work equally fine on any other GNU/Linux distro as much as
[requirements](#requirements) are accomplished.

Includes `virtnbdbackup`, `virtnbdrestore` and similar utils, installed along
with their required dependencies. Other utilities, such as latest Qemu Utils
and OpenSSH Client, are also included to leverage all available features.

Currently, is being built from latest `debian:trixie-slim` official image.

## Requirements

- Docker Engine on the host server. See [Docker
  Documentation](https://docs.docker.com/get-docker/) for further instructions
- Libvirt >=v6.0.0. on the host server (minimal). A version >=7.6.0 is
  necessary to avoid [patching XML VM
  definitions](../README.md#libvirt-versions--760-debian-bullseye-ubuntu-20x)
- Qemu Guest Agent installed and running inside the guest OS. For *NIX guests,
  use the latest available version according the distro (installed by default
  on Debian 12 when provisioned via ISO). For Windows guests, install latest
  [VirtIO
  drivers](https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/archive-virtio/)

## Bind mounts:

*All the trick consists into set the right bind mounts for your host OS case*

- Virtnbdbackup needs to access libvirt's socket in order to work correctly,
  and attempts this via `/var/run/libvirt` path.

  In basically all mainstream distros of today (Debian, RedHat, Archlinux and
  the countless distros based on these) as in this image, `/var/run` is a
  symlink to `/run` and `/var/lock` a symlink to `run/lock`.  Therefore, for
  the vast majority of scenarios the correct bind mount is: `-v /run:/run`

  But in some operating systems, `/run` and `/var/run` are still separated
  folders. Under this scenario you need to bind mount with `-v /var/run:/run`
  And most likely, you will need to mount with either `-v /var/lock:/run/lock`
  or `-v /var/run/lock:/run/lock` in order to run this container correctly.

  If you're in trouble with this, read [Main FAQ](../README.md#faq) first, and
  identify the error you're getting in order to set the correct bind mounts
  that work for the specific host that serves Docker.

- Virtnbdbackup and virtnbdrestore create sockets for backup/restoration jobs
  tasks at `/var/tmp`. Ensure to *always* add a bind mount with `-v
  /var/tmp:/var/tmp`

- When working with VMs that require to boot with UEFI emulation (e.g. Windows
  10 and up), additional bind mounts are needed:

  Path to `/etc/libvirt/qemu/nvram` is required to backup/restore nvram files
  per VM (which seems to be the same on Qemu implementations tested so far)

  Path to your distro correspondent OVMF files. This is `/usr/share/OVMF` on
  Debian based, and `/usr/share/qemu/ovmf-x64` on Unraid (feel free to report
  this path on other distributions)

- Finally, using identical *host:container* bind mounts for virtual disk
  locations (as well nvram & ovmf binaries, when applies), is necessary to
  allow backup/restore commands to find out the files at the expected
  locations, in concordance with VM definitions at the host side.

## Usage Examples

For detailed info about options, also see
[backup](../README.md#backup-examples) and
[restoration](../README.md#restoration-examples) examples

### Full or incremental backup:

```
docker run --rm \
-v /run:/run \
-v /var/tmp:/var/tmp \
-v /etc/libvirt/qemu/nvram:/etc/libvirt/qemu/nvram \
-v /usr/share/OVMF:/usr/share/OVMF \
-v /<path-to-backups>:/backups \
ghcr.io/abbbi/virtnbdbackup:master \
virtnbdbackup -d <domain> -l auto -o /backups/<domain>
```

Where `<path-to-backups>` is an example of the actual master backups folder
where VM sub-folders are being stored in your system, and `<domain>` the VM
name (actual path to disk images is not required.)

### Full Backup Restoration to an existing VM:

```
docker run --rm \
-v /run:/run \
-v /var/tmp:/var/tmp \
-v /etc/libvirt/qemu/nvram:/etc/libvirt/qemu/nvram \
-v /usr/share/OVMF:/usr/share/OVMF \
-v /mnt/backups:/backups \
-v /<path-to-virtual-disks>:/<path-to-virtual-disks> \
ghcr.io/abbbi/virtnbdbackup:master \
bash -c \
"mkdir -p /<path-to-virtual-disks>/<domain>.old && \
mv /<path-to-virtual-disks>/<domain>/* /<path-to-virtual-disks>/<domain>.old/ && \
virtnbdrestore -i /backups/<domain> -o /<path-to-virtual-disks>/<domain>"
```

Where `/<path-to-virtual-disks>/<domain>` is the actual folder where the
specific disk image(s) of the VM to restore, are stored on the host system. In
this case, bind mounts should be identical.

On this example, any existing files are being moved to a folder named
`<domain>.old`, because restore would fail if it finds the same image(s) that
is attempting to restore onto the destination. For instance, you might opt to
operate with existing images according your needs, e.g. deleting it before to
restore from backup.

## Interactive Mode:

This starts a session inside a (volatile) container, provisioning all bind
mounts and allowing to do manual backups and restores, as well
testing/troubleshooting:

```
docker run -it --rm \
-v /run:/run \
-v /var/tmp:/var/tmp \
-v /etc/libvirt/qemu/nvram:/etc/libvirt/qemu/nvram \
-v /usr/share/OVMF:/usr/share/OVMF \
-v /mnt/backups:/backups \
-v /<path-to-virtual-disks>:/<path-to-virtual-disks> \
ghcr.io/abbbi/virtnbdbackup \
bash
```
