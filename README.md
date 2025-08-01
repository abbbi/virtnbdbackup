![ci](https://github.com/abbbi/virtnbdbackup/actions/workflows/ci-ubuntu-latest.yml/badge.svg)
[![package-build](https://github.com/abbbi/virtnbdbackup/actions/workflows/build.yml/badge.svg)](https://github.com/abbbi/virtnbdbackup/actions/workflows/build.yml)

# virtnbdbackup

Backup utility for `libvirt`, using the latest changed block tracking features.
Create online, thin provisioned full and incremental or differential backups
of your `kvm/qemu` virtual machines.

![Alt text](screenshot.jpg?raw=true "Title")

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [About](#about)
- [Prerequisites](#prerequisites)
  - [Libvirt versions <= 7.6.0 (Debian Bullseye, Ubuntu 20.x)](#libvirt-versions--760-debian-bullseye-ubuntu-20x)
  - [RHEL/Centos Stream, Alma, Rocky Linux](#rhelcentos-stream-alma-rocky-linux)
    - [Version <= 8.5](#version--85)
    - [Version >= 8.6](#version--86)
  - [Environment dependencies](#environment-dependencies)
- [Installation](#installation)
  - [Python package](#python-package)
  - [RPM package](#rpm-package)
  - [Debian package](#debian-package)
  - [Virtualenv](#virtualenv)
  - [Docker images](#docker-images)
- [Backup modes and concept](#backup-modes-and-concept)
- [Incremental backups of RAW disks and direct attached volumes (LVM, ZFS, ..)](#incremental-backups-of-raw-disks-and-direct-attached-volumes-lvm-zfs-)
  - [QCOW Format versions](#qcow-format-versions)
  - [Libvirt versions < v10.10.0](#libvirt-versions--v10100)
  - [Libvirt versions >= v10.10.0](#libvirt-versions--v10100)
- [Backup Examples](#backup-examples)
  - [Local full/incremental backup](#local-fullincremental-backup)
  - [Backing up offline virtual domains](#backing-up-offline-virtual-domains)
  - [Application consistent backups](#application-consistent-backups)
  - [Rotating backups](#rotating-backups)
  - [Excluding disks](#excluding-disks)
  - [Estimating differential/incremental backup size](#estimating-differentialincremental-backup-size)
  - [Backup threshold](#backup-threshold)
  - [Backup concurrency](#backup-concurrency)
  - [Compression](#compression)
  - [Remote Backup](#remote-backup)
    - [QEMU Sessions](#qemu-sessions)
    - [NBD with TLS (NBDSSL)](#nbd-with-tls-nbdssl)
    - [Using a separate network for data transfer](#using-a-separate-network-for-data-transfer)
    - [Piping data to other hosts](#piping-data-to-other-hosts)
  - [Kernel/initrd and additional files](#kernelinitrd-and-additional-files)
- [Restore examples](#restore-examples)
  - [Dumping backup information](#dumping-backup-information)
  - [Verifying created backups](#verifying-created-backups)
  - [Complete restore](#complete-restore)
  - [Process only specific disks during restore](#process-only-specific-disks-during-restore)
  - [Point in time recovery](#point-in-time-recovery)
  - [Restoring with modified virtual machine config](#restoring-with-modified-virtual-machine-config)
  - [Remote Restore](#remote-restore)
- [Post restore steps and considerations](#post-restore-steps-and-considerations)
- [Single file restore and instant recovery](#single-file-restore-and-instant-recovery)
- [Transient virtual machines: checkpoint persistency on clusters](#transient-virtual-machines-checkpoint-persistency-on-clusters)
- [Supported Hypervisors](#supported-hypervisors)
  - [Ovirt, RHEV or OLVM](#ovirt-rhev-or-olvm)
  - [OpenNebula](#opennebula)
- [Authentication](#authentication)
- [Internals](#internals)
  - [Backup Format](#backup-format)
  - [Extents](#extents)
  - [Backup I/O and performance: scratch files](#backup-io-and-performance-scratch-files)
  - [Debugging](#debugging)
- [FAQ](#faq)
  - [The thin provisioned backups are bigger than the original qcow images](#the-thin-provisioned-backups-are-bigger-than-the-original-qcow-images)
  - [Backup fails with "Cannot store dirty bitmaps in qcow2 v2 files"](#backup-fails-with-cannot-store-dirty-bitmaps-in-qcow2-v2-files)
  - [Backup fails with "unable to execute QEMU command 'transaction': Bitmap already exists"](#backup-fails-with-unable-to-execute-qemu-command-transaction-bitmap-already-exists)
  - [Backup fails with "Bitmap inconsistency detected: please cleanup checkpoints using virsh and execute new full backup"](#backup-fails-with-bitmap-inconsistency-detected-please-cleanup-checkpoints-using-virsh-and-execute-new-full-backup)
  - [Backup fails with "Error during checkpoint removal: [internal error: bitmap 'XX' not found in backing chain of 'XX']"](#backup-fails-with-error-during-checkpoint-removal-internal-error-bitmap-xx-not-found-in-backing-chain-of-xx)
  - [Backup fails with "Virtual machine does not support required backup features, please adjust virtual machine configuration."](#backup-fails-with-virtual-machine-does-not-support-required-backup-features-please-adjust-virtual-machine-configuration)
  - [Backup fails with "Timed out during operation: cannot acquire state change lock"](#backup-fails-with-timed-out-during-operation-cannot-acquire-state-change-lock)
  - [Backup fails with "Failed to bind socket to /var/tmp/virtnbdbackup.XX: Permission denied"](#backup-fails-with-failed-to-bind-socket-to-vartmpvirtnbdbackupxx-permission-denied)
  - [High memory usage during backup](#high-memory-usage-during-backup)
  - [fstrim and (incremental) backup sizes](#fstrim-and-incremental-backup-sizes)
  - [Test your backups!](#test-your-backups)
  - [Links](#links)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->


# About

Existing backup solutions or scripts for `libvirt/kvm` usually depend on the
external snapshot feature to create backups, sometimes even require to
shutdown or pause the virtual machine.

Recent additions to both the `libvirt` and `qemu` projects have introduced new
capabilities that allow to create online (full and incremental) backups, by
using so called `dirty bitmaps` (or changed block tracking).

`virtnbdbackup` uses these features to create online full and incremental
or differential backups.

`virtnbdrestore` can be used to re-construct the complete image from the
thin provisioned backups.

`virtnbdmap` can be used to map an thin provisioned backup image into a
block device on-the-fly, for easy single file restore or even instant
boot from an backup image.

For backing up standalone qemu virtual machines not managed by libvirt, see
this project: [qmpbackup](https://github.com/abbbi/qmpbackup)

# Prerequisites

Obviously you require a libvirt/qemu version that supports the incremental
backup features. Since libvirt v7.6.0 and qemu-6.1 the required features are
[enabled by default](https://libvirt.org/news.html#v7-6-0-2021-08-02) and are
considered production ready: everything will work out of the box.

Following, you will find a short overview which older libvirt
versions may require further adjustments to the virtual machine config.


## Libvirt versions <= 7.6.0 (Debian Bullseye, Ubuntu 20.x)

If you are using Debian Bullseye or Ubuntu 20.x, the included libvirt version
already has an almost complete support for incremental backup, although it
doesn't work properly with migration or some block jobs.

If you don't want to use migration or other blockjobs you can enable the 
incremental backup feature on these libvirt versions. Change the virtual
machine config using `virsh edit <vm>` like so: (the first line must be 
changed, too!):

 ```
  <domain type='kvm' id='1' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
  [..]
  <qemu:capabilities>
    <qemu:add capability='incremental-backup'/>
  </qemu:capabilities>
  [..]
  </domain>
 ```

`Note`:
> You must power cycle the virtual machine after enabling the feature!
> Upstream libvirt strongly discourages enabling the feature on production
> systems for these libvirt versions.

## RHEL/Centos Stream, Alma, Rocky Linux

### Version <= 8.5

Up to RHEL/Centos8/Almalinux 8.5, libvirt packages from the advanced
virtualization stream support all required features. To install libvirt from
the stream use:

  ```
  yum install centos-release-advanced-virtualization
  yum makecache
  yum module install virt
  ```

and enable the feature by adjusting the virtual machine config.

### Version >= 8.6

As of RHEL 8.6, the advanced virtualization stream has been deprecated,
and all components supporting the new feature are included in the
virt:rhel module, the feature is enabled by default. [(Details)](https://access.redhat.com/solutions/6959344)

## Environment dependencies
 
 * python libvirt module version  >= 6.0.0 (yum install python3-libvirt)
 * python libnbd bindings (https://github.com/libguestfs/libnbd) version >= `1.5.5` (yum install python3-libnbd)
 * The virtual machine should use qcow version 3 images to support the full feature set.
 
# Installation

There are several ways to install the utility, below you will find an short
description for each of them. For Debian and RHEL/SuSE based derivates see
[releases](https://github.com/abbbi/virtnbdbackup/releases) for pre-built
packages.

`Note`:
> Please consider to check [past issues related to
> installation](https://github.com/abbbi/virtnbdbackup/issues?q=is%3Aissue+is%3Aclosed+label%3Ainstallation)
> if you face any troubles before opening a new issue.

## Python package
```
 git clone https://github.com/abbbi/virtnbdbackup && cd virtnbdbackup
 pip install .
```

`Note`:
> Do not install the "nbd" package available on PyPI, it does not provide the
> required nbd bindings (unfortunately has the same name). You have to
> additionally install the provided python3-libnbd packages by your
> distribution, or compile the libnbd bindings by yourself.

## RPM package

Packages for RHEL/Fedora and OpenSUSE are available via
[releases](https://github.com/abbbi/virtnbdbackup/releases).

To create an RPM package from source by yourself you can follow the steps from
the github [build
workflow](https://github.com/abbbi/virtnbdbackup/actions/workflows/build.yml).


## Debian package

Official packages are available:
[https://packages.debian.org/virtnbdbackup](http://packages.debian.org/virtnbdbackup) and are maintained on
the [Debian salsa codespace](https://salsa.debian.org/debian/virtnbdbackup).

For the latest packages available check
[releases](https://github.com/abbbi/virtnbdbackup/releases).

To create an Debian package from source by yourself you can follow the steps
from the github [build
workflow](https://github.com/abbbi/virtnbdbackup/actions/workflows/build.yml).


## Virtualenv

For setup within an virtualenv see [venv scripts](venv/).

## Docker images

You can build an docker image using the existing [Dockerfile README](docker/)

All released versions and master branch are published via github container
registry, too. Example:

```
 docker run -it ghcr.io/abbbi/virtnbdbackup:master virtnbdbackup
```

See [packages](https://github.com/abbbi/virtnbdbackup/pkgs/container/virtnbdbackup).

# Backup modes and concept

Following backup modes can be used:

* `auto`: If the target folder is empty, attempt to execute full backup,
  otherwise switch to backup mode incremental: allows rotation of backup
  into monthly folders.

* `full`: Full, thin provisioned backup of the virtual machine, a new checkpoint
  named `virtnbdbackup` will be created, all existent checkpoints from prior
  backups matching this name will be removed: a new backup chain is created.
  The Virtual machine must be online and running for this backup mode to work.

* `copy`: Full, thin provisioned backup of the virtual machine disks, no
  checkpoint is created for further incremental backups, existing checkpoints
  will be left untouched. This is the default mode and works with qcow images
  not supporting persistent bitmaps.

* `inc`: Perform incremental backup, based on the last full or incremental
  backup. A checkpoint for each incremental backup is created and saved.

* `diff`: Perform differential backup: saves the current delta to the last
  incremental or full backup.

All required information for restore is stored to the same directory,
including the latest virtual machine configuration, checkpoint information,
disk data and logfiles.

The target directory must be rotated if a new backup set is created.

If the virtual domain is active and running, a backup job operation via
`libvirt api` is started, which in turn initializes a new nbd server backend
listening on a local unix socket. This nbd backend provides consistent access
to the virtual machines, disk data and dirty blocks. After the backup process
finishes, the job is stopped and the nbd server quits operation.

It is possible to backup multiple virtual machines on the same host system at
the same time, using separate calls to the application with a different target
directory to store the data.

# Incremental backups of RAW disks and direct attached volumes (LVM, ZFS, ..)

## QCOW Format versions

`libvirt/qemu` support dirty bitmaps, required for incremental backups only
with qcow(v3) based disk images. If you are using older image versions, you can
only create `copy` backups, or consider converting the images to a newer format
using `qemu-img`:

> qemu-img convert -O qcow2 -o compat=1.1 disk-old.qcow2 disk.qcow2


## Libvirt versions < v10.10.0

Older versions of `libvirt/qemu` do not support creation of checkpoints
for direct attached volumes or RAW images, as there is no way to 
persistently store the bitmap information.

By default `virtnbdbackup` will exclude all disks with format `raw` as well
as direct attached (passthrough) disks such as LVM or ZVOL and ISCSI
volumes. 

This behavior can be changed if option `--raw` is specified, raw disks will
then be included during a `full` backup. This of course means that no thin
provisioned backup is created for these particular disks.

During restore, these files can be copied "as is" from the backup folder and
must not be processed using `virtnbdrestore`.

`Note:`
> The backup data for raw disks will only be crash consistent, be aware
> that this might result in inconsistent filesystems after restoring!

## Libvirt versions >= v10.10.0

Recent libvirt versions have added the possibility to use a so called
"data-file" setting for QCOW images. By doing this, a QCOW image is used for
metadata storage and is configured as the virtual machines primary disk, but
the the data of the virtual machine is stored in whatever storage is specified
as "data-file" setting (LVM Volumes, RAW images, ZFS Volumes, RBD ..)

Now, the metadata qcow image can be used for persistent bitmap storage,
thus allowing to create incremental backups for RAW backend devices, too.

In order to make this work, you need to ajdust you virtual machine
configuration. A short example is outlined below:

 1) You need to create a QCOW image that has a data-file setting, matching the
    virtual size of your RAW device:

```
 # point the data-file to a temporary file, as create will overwrite whatever it finds here
 qemu-img create -f qcow2 /tmp/metadata.qcow2 -o data_file=/tmp/TEMPFILE,data_file_raw=true ..
 rm -f /tmp/TEMPFILE
```

 2) Modify the qcow image to point to whatever RAW device you have your virtual machine
 disk data on:

```
 qemu-img amend /tmp/metadata.qcow2 -o data_file=/your/original/volume.raw,data_file_raw=true
```

 3) Adjust your virtual machines disk configuration and point the disk to the metadata
 device, adding additional information about the data-file backend:

```
     <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2' cache='none' io='native' discard='unmap'/>
      <source file='/tmp/metadata.qcow2'>
        <dataStore type='file'>
          <format type='raw'/>
          <source file='/your/original/volume.raw'/>
        </dataStore>
      </source>
      <target dev='vda' bus='virtio'/>
    </disk>
```

From this point on, you can use mostly all features for backup that regular
QCOW images support: doing incremental backups.

`Note:`
> One Limitation: FULL backups for these devices will always be full
> provisioned, as in the complete RAW image.


# Backup Examples

Each backup for a virtual machine must be saved to an individual target
directory. Once the target directory includes an full backup, it can be used as
base for further incremental or differential backups.

## Local full/incremental backup

Start full backup of domain `vm1`, save data to `/tmp/backupset/vm1`:

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset/vm1
```

Start incremental backup for domain `vm1`, backup only changed blocks to the
last full backup, the same directory is used as backup target:

```
virtnbdbackup -d vm1 -l inc -o /tmp/backupset/vm1
```

The resulting directory will contain both backups and all other files required
to restore the virtual machine. Created logfiles can be used for analyzing
backup issues:

```
/tmp/backupset/vm1
├── backup.full.05102021161752.log
├── backup.inc.05102021161813.log
├── checkpoints
│   ├── virtnbdbackup.0.xml
│   ├── virtnbdbackup.1.xml
├── sda.full.data
├── sda.inc.virtnbdbackup.1.data
├── vm1.cpt
├── vmconfig.virtnbdbackup.0.xml
├── vmconfig.virtnbdbackup.1.xml
```

## Backing up offline virtual domains

If the virtual domain is not in running state (powered off) `virtnbdbackup`
supports `copy` and `inc/diff` backup modes. Incremental and differential
backups will then save the changed blocks since last created checkpoint.

Backup mode `full` is changed to mode `copy`, because libvirt does not allow to
create checkpoints for offline domains.

This behavior can be changed using the `-S` (`--start-domain`) option: prior to
executing the backup, the virtual domain will then be started in `paused` state
for the time the backup is created: The virtual machines CPU's are halted, but
the running QEMU Process will allow all operations required to execute backups.

Using this option will allow for all range of backup types (full/diff/inc) and
makes most sense if used with the backup mode `auto`.

Also, the option won't alter the virtual domain state if it is already online,
thus it can be used for backing up virtual machines whose state is unknown
prior to backup.

## Application consistent backups

During backup `virtnbdbackup` attempts to freeze all file systems within the
domain using the qemu guest agent filesystem freeze and thaw functions.  In
case no qemu agent is installed or filesystem freeze fails, a warning is shown
during backup:

```
WARNING [..] Guest agent is not responding: QEMU guest agent is not connected
```

In case you receive this warning, check if the qemu agent is installed and
running in the domain.

It is also possible to specify one or multiple mountpoints used within
the virtual machine to freeze only specific filesystems, like so:

`virtnbdbackup -d vm1 -l inc -o /tmp/backupset/vm1 -F /mnt,/var`

this way only the underlying filesystems on */mnt* and */var* are frozen
and thawed.

`Note:`
> It is highly recommended to have an qemu agent running in the virtual
> domain to ensure file system consistency during backup!


## Rotating backups

With backup mode `auto` it is possible to have a monthly rotation/retention.  If
the target folder is empty, backup mode auto will create an full backup. On the
following executions, it will automatically switch to backup mode incremental,
if the target folder already includes an full backup. Example:

```
virtnbdbackup -d vm1 -l auto -o /tmp/2022-06 -> creates full backup
virtnbdbackup -d vm1 -l auto -o /tmp/2022-06 -> creates inc backup
virtnbdbackup -d vm1 -l auto -o /tmp/2022-06 -> creates inc backup
virtnbdbackup -d vm1 -l auto -o /tmp/2022-07 -> creates full backup
virtnbdbackup -d vm1 -l auto -o /tmp/2022-07 -> creates inc backup
```

## Excluding disks

Option `-x` can be used to exclude certain disks from the backup. The name of
the disk to be excluded must match the disks target device name as configured
in the domains xml definition, for example:

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset/vm1 -x sda
```

Special devices such as `cdrom/floppy` or `direct attached luns` are excluded
by default, as they are not supported by the changed block tracking layer.

It is also possible to only backup specific disks using the include option
(`--include`, or `-i`):

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset/vm1 -i sdf
```

## Estimating differential/incremental backup size

Sometimes it can be useful to estimate the data size prior to executing the
next `incremental` or `differential` backup. This can be done by using the
option `-p` which will query the virtual machine checkpoint information for the
current size:

```
virtnbdbackup -d vm1 -l inc -o /tmp/backupset/vm1 -p
[..]
[..] INFO virtnbdbackup - handleCheckpoints [MainThread]: Using checkpoint name: [virtnbdbackup.1].
[..] INFO virtnbdbackup - main [MainThread]: Estimated checkpoint backup size: [24248320] Bytes
```

`Note:`
> Not all libvirt versions support the flag required to read the checkpoint
> size. If the estimated checkpoint size is always 0, your libvirt version
> might miss the required features.

## Backup threshold

If an `incremental` or `differential` backup is attempted and the virtual machine
is active, it is possible to specify an threshold for executing the backup
using the `--threshold` option. The backup will then only be executed if the
amount of data changed meets the specified threshold (in bytes):

```
virtnbdbackup -d vm1 -l inc -o /tmp/backupset/vm1 --threshold 3311264
[..]
[..] INFO virtnbdbackup - handleCheckpoints [MainThread]: Using checkpoint name: [virtnbdbackup.1].
[..] ]virtnbdbackup - main [MainThread]: Backup size [3211264] does not meet required threshold [3311264], skipping backup.
```

## Backup concurrency

If `virtnbdbackup` saves data to a regular target directory, it starts one
thread for each disk it detects to speed up the backup operation.

This behavior can be changed using the `--worker` option to define an amount of
threads to be used for backup. Depending on how many disks your virtual machine
has attached, it might make sense to try a different amount of workers to see
which amount your hardware can handle best.

If standard output (`-`) is defined as backup target, the amount of workers is
always limited to 1, to ensure a valid Zip file format.

## Compression

It is possible to enable compression for the `stream` format via `lz4`
algorithm by using the `--compress` option. The saved data is compressed inline
and the saveset file is appended with compression trailer including information
about the compressed block offsets. By default compression level `2` is set if
no parameter is applied. Higher compression levels can be set via:

 `--compress=16`

During the restore, `virtnbdrestore` will automatically detect such compressed
backup streams and attempts to decompress saved blocks accordingly.

Using compression will come with some CPU overhead, both lz4 checksums for
block and original data are enabled.

## Remote Backup

It is also possible to backup remote libvirt systems. The most convenient way
is to use ssh for initiating the libvirt connection (key authentication
mandatory).

Before attempting an remote backup, please validate your environment meets the
following criteria:

 * DNS resolution (forward and reverse) must work on all involved systems.
 * SSH Login to the remote system via ssh key authentication (using ssh agent
   or passwordless ssh key) should work without issues.
 * Unique hostnames must be set on all systems involved.
   ([background](https://github.com/abbbi/virtnbdbackup/issues/117))
 * Firewall must allow connection on all ports involved.

If the virtual machine has additional files configured, as described in
[Kernel/initrd and additional files](#kernelinitrd-and-additional-files), these
files will be copied from the remote system via SSH(SFTP).

### QEMU Sessions

In order to backup virtual machines from a remote host, you must specify an
[libvirt URI](https://libvirt.org/uri.html) to the remote system.

The following example saves the virtual machine `vm1` from the remote libvirt
host `hypervisor` to the local directory `/tmp/backupset/vm1`, it uses the `root`
user for both the libvirt and ssh authentication:

```
virtnbdbackup -U qemu+ssh://root@hypervisor/system --ssh-user root -d vm1 -o  /tmp/backupset/vm1
```

See also: [Authentication](#authentication)

`Note`:
> If you want to run multiple remote backups at the same time you need to pass
> an unique port for the NBD service used for data transfer via --nbd-port
> option for each backup session.

### NBD with TLS (NBDSSL)

By default disk data received from a remote system will be transferred via
regular NBD protocol. You can enable TLS for this connection, using the `--tls`
option. Before being able to use TLS, you *must* configure the required
certificates on both sides. [See this
script](https://github.com/abbbi/virtnbdbackup/blob/master/scripts/create-cert.sh).

See the following documentation by the libvirt project for detailed
instructions how setup:

 https://wiki.libvirt.org/page/TLSCreateCACert

`Note:`
> You should have installed at least version 1.12.6 of the libnbd library
> which makes the transfer via NBDS more stable [full background](https://github.com/abbbi/virtnbdbackup/issues/66#issuecomment-1196813750)

### Using a separate network for data transfer

In case you want to use a dedicated network for the data transfer via NBD, you
can specify an specific IP address to bind the remote NBD service to via
`--nbd-ip` option.

### Piping data to other hosts

If the output target points to standard out (`-`), `virtnbdbackup` puts the
resulting backup data into an uncompessed zip archive.

A such, it is possible to transfer the backup data to different hosts, or pipe
it to other programs.

However, keep in mind that in case you want to perform incremental backups, you
must keep the checkpoint files on the host you are executing the backup utility
from, until you create another full backup.

If output is set to standard out, `virtnbdbackup` will create the required
checkpoint files in the directory it is executed from.

Here is an example:

```
 # mkdir backup-weekly; cd backup-weekly
 # virtnbdbackup -d vm1 -l full -o - | ssh root@remotehost 'cat > backup-full.zip'
 # [..]
 # INFO outputhelper - __init__: Writing zip file stream to stdout
 # [..]
 # INFO virtnbdbackup - main: Finished
 # INFO virtnbdbackup - main: Adding vm config to zipfile
 # [..]
```

Any subsequent incremental backup operations must be called from within this
directory:

```
 # cd backup-weekly
 # virtnbdbackup -d vm1 -l inc -o - | ssh root@remotehost 'cat > backup-inc1.zip'
 [..]
```

You may consider adding the created checkpoint files to some VCS system,
like git, to have some kind of central backup history tracking.

During restore unzip the data from both zip files into a single directory:
(use `virtnbdrestore` to reconstruct the virtual machine images):

```
 # unzip -o -d restoredata backup-full.zip
 # unzip -o -d restoredata backup-inc1.zip
```


## Kernel/initrd and additional files

If an domain has configured custom kernel, initrd, loader or nvram images
(usually the case if the domain boots from OVM UEFI BIOS), these files will be
saved to the backup folder as well.

# Restore examples

For restoring, `virtnbdrestore` can be used. It reconstructs the streamed
backup format back into a usable qemu qcow image.

The restore process will create a qcow image with the original virtual size.

In a second step, the qcow image is then mapped to a ndb server instance where
all data blocks are sent to and are applied accordingly. The resulting image
can be mounted (using `guestmount`) or attached to a running virtual machine in
order to recover required files.

## Dumping backup information

As a first start, the `dump` parameter can be used to dump the saveset
information of an existing backup:

```
virtnbdrestore -i /tmp/backupset/vm1 -o dump
INFO:root:Dumping saveset meta information
{'checkpointName': 'virtnbdbackup',
 'dataSize': 704643072,
 'date': '2020-11-15T20:50:36.448938',
 'diskName': 'sda',
 'incremental': False,
 'parentCheckpoint': False,
 'streamVersion': 1,
 'virtualSize': 32212254720}
[..]
```
The output includes information about the thick and thin provisioned disk
space that is required for recovery, date of the backup and checkpoint chain.

## Verifying created backups

As with version >= 1.9.40  `virtnbdbackup` creates an check sum for each
created data file. Using `virtnbdrestore` you can check the integrity for the
created data files without having to restore:

```
virtnbdrestore -i /tmp/backup/vm1 -o verify
[..] INFO lib common - printVersion [MainThread]: Version: 1.9.39 Arguments: ./virtnbdrestore -i /tmp/backup/vm1 -o verify
[..] INFO root virtnbdrestore - verify [MainThread]: Computing checksum for: /tmp/backup/vm1/sda.full.data
[..] INFO root virtnbdrestore - verify [MainThread]: Checksum result: 541406837
[..] INFO root virtnbdrestore - verify [MainThread]: Comparing checksum with stored information
[..] INFO root virtnbdrestore - verify [MainThread]: OK
```

this makes it easier to spot corrupted backup files due to storage issues.
([background](https://github.com/abbbi/virtnbdbackup/issues/134))

## Complete restore

To restore all disks within the backupset into a usable qcow image use
command:

```
virtnbdrestore -i /tmp/backupset/vm1 -o /tmp/restore
```

All incremental backups found will be applied to the target images
in the output directory `/tmp/restore`

`Note`:
> The restore utility will copy the latest virtual machine config to the
> target directory, but won't alter its contents. You have to adjust the config
> file for the new paths and/or excluded disks to be able to define and run it.

`Note`:
> Created disk images will be thin provisioned by default, you can change this
> behavior using option `--preallocate` to create thick provisioned images.

## Process only specific disks during restore

A single disk can be restored by using the option `-d`, the disk name has
to match the virtual disks target name, for example:

```
virtnbdrestore -i /tmp/backupset/vm1 -o /tmp/restore -d sda
```

## Point in time recovery

Option `--until` allows to perform a point in time restore up to the desired
checkpoint. The checkpoint name has to be specified as reported by the
dump output (field `checkpointName`), for example:

```
virtnbdrestore -i /tmp/backupset/vm1 -o /tmp/restore --until virtnbdbackup.2
```

It is also possible to specify the source data files specifically used for the
rollback via `--sequence` option, but beware: you must be sure the sequence you
apply has the right order, otherwise the restored image might be errnous,
example:

```
virtnbdrestore -i /tmp/backupset/vm1 -o /tmp/restore --sequence vdb.full.data,vdb.inc.virtnbdbackup.1.data
```

## Restoring with modified virtual machine config

Option `-c` can be used to adjust the virtual machine configuration during
restore accordingly, the following changes are done:

 * UUID of the virtual machine is removed from the config file
 * Name of the virtual machine is prefixed with "restore_" (use option
   `--name` to specify desired vm name)
 * The disk paths to the virtual machine are changed to the new target directory.
 * If virtual machine was operating on snapshots/backing store images, the
   references to the configured backing stores will be removed.
 * If the virtual machine disk has configured a data-file/diskStore backend,
   the paths in the created qcow image and vm config will be adjusted
   accordingly.
 * Raw devices are removed from VM config if `--raw` is not specified, as well
   as floppy or cdrom devices (which aren't part of the backup).

`Note:`
> If missing, Kernel, UEFI or NVRAM files are restored to their original
> location as set in the virtual machine configuration.

A restored virtual machine can then be defined and started right from the
restored directory (or use option `-D` to define automatically):

```
virtnbdrestore -c -i /tmp/backupset/vm1 -o /tmp/restore
[..]
[..] INFO virtnbdrestore - restoreConfig [MainThread]: Adjusted config placed in: [/tmp/restore/vmconfig.virtnbdbackup.0.xml]
[..] INFO virtnbdrestore - restoreConfig [MainThread]: Use 'virsh define /tmp/restore/vmconfig.virtnbdbackup.0.xml' to define VM
```

## Remote Restore

Restoring to a remote host is possible too, same options as during backup
apply. The following example will restore the virtual machine from the local
directory `/tmp/backupset` to the remote system "hypervisor", alter its
configuration and register the virtual machine:

```
virtnbdrestore -U qemu+ssh://root@hypervisor/system --ssh-user root -cD -i /tmp/backupset/vm1 -o /remote/target
```

# Post restore steps and considerations

If you restore the virtual machine with its original name on the same
hypervisor, you may have to cleanup checkpoint information, otherwise backing
up the restored virtual machine may fail, see [this
discussion](https://github.com/abbbi/virtnbdbackup/discussions/48)


# Single file restore and instant recovery

The `virtnbdmap` utility can be used to map uncompressed backup images from the
stream format into an accessible block device on the fly. This way, you can
restore single files or even boot from an existing backup image without having
to restore the complete dataset.

The utility requires `nbdkit with the python plugin` to be installed on the
system along with required qemu tools (`qemu-nbd`) and an loaded nbd kernel
module. It must be executed with superuser (root) rights or via sudo.

The following example maps an existing backup image to the network block
device `/dev/nbd0`:

```
 # modprobe nbd max_partitions=15
 # virtnbdmap -f /backupset/vm1/sda.full.data
 [..] INFO virtnbdmap - <module> [MainThread]: Done mapping backup image to [/dev/nbd0]
 [..] INFO virtnbdmap - <module> [MainThread]: Press CTRL+C to disconnect
```

While the process is running, you can access the backup image like a regular
block device:

```
fdisk -l /dev/nbd0
Disk /dev/nbd0: 2 GiB, 2147483648 bytes, 4194304 sectors
```

You can also create an mapped "point in time" recovery image by passing a
sequence of full and incremental backups as parameter. The changes from the
incremental backups will then be replayed to the block device on the fly and
the image will represent the latest state:

```
virtnbdmap -f /backupset/vm1/sda.full.data,/backupset/vm1/sda.inc.virtnbdbackup.1.data,/backupset/vm1/sda.inc.virtnbdbackup.2.data
[..]
[..] INFO virtnbdmap - main [MainThread]: Need to replay incremental backups
[..] INFO virtnbdmap - main [MainThread]: Replaying offset 420 from /backup/sda.inc.virtnbdbackup.1.data
[..] INFO virtnbdmap - main [MainThread]: Replaying offset 131534 from /backup/sda.inc.virtnbdbackup.1.data
[..]
[..] INFO virtnbdmap - main [MainThread]: Replaying offset 33534 from /backup/sda.inc.virtnbdbackup.2.data
[..] INFO virtnbdmap - <module> [MainThread]: Done mapping backup image to [/dev/nbd0]
[..] INFO virtnbdmap - <module> [MainThread]: Press CTRL+C to disconnect
[..]
```

The original image will be left untouched as nbdkits copy on write filter is
used to replay the changes.

Further you can create an overlay image via `qemu-img` and boot from it right
away (or boot directly from the /dev/nbd0 device).

```
qemu-img create -b /dev/nbd0 -f qcow2 bootme.qcow2
qemu-system-x86_64 -enable-kvm -m 2000 -hda bootme.qcow2
```

To remove the mappings, stop the utility via "CTRL-C"

`Note`:
> If the virtual machine includes volume groups, the system will attempt to
> set them online as you create the mapping, because the copy on write device 
> is writable by default.
> If your host system is using the same volume group names this could lead to
> issues (check `dmesg` or `journalctl` then).
> In case the volume groups are online, it is recommended to change them to
> offline just before you remove the mapping, to free all references to the
> mapped nbd device (`vgchange -a n <vg_name>`)

`Note`:
> If you map the image device with the `--readonly` option you may need to pass
> certain options to the mount command (-o norecovery,ro) in order to be able
> to mount the filesystems. This may also be the case if no qemu agent was
> installed within the virtual machine during backup.

# Transient virtual machines: checkpoint persistency on clusters

In case virtual machines are started in transient environments, such as using
cluster solutions like `pacemaker` situations can appear where the checkpoints
for the virtual machine defined by libvirt are not in sync with the bitmap
information in the qcow files.

In case libvirt creates a checkpoint, the checkpoint information is stored
in two places:

 * var/lib/libvirt/qemu/checkpoint/<domain_name> 
 * In the bitmap file of the virtual machines qcow image.

Depending on the cluster solution, in case virtual machines are destroyed
on host A and are re-defined on host B, libvirt loses the information about
those checkpoints. Unfortunately `libvirtd` scans the checkpoint only once
during startup.

This can result in a situation, where the bitmap is still defined in the
qcow image, but libvirt doesn't know about the checkpoint, backup then
fails with:

`Unable to execute QEMU command 'transaction': Bitmap already exists`

By default `virtnbdbackup` attempts to store the checkpoint information in the
default backup directory, in situations where it detects a checkpoint is
missing, it attempts to redefine them from the prior backups.

In order to store the checkpoint information at some central place the option
`--checkpointdir` can be used, this allows having persistent checkpoints
stored across multiple nodes:

As example:

 1) Create backup on host A, store checkpoints in a shared directory between
 hosts in `/mnt/shared/vm1`:

`virtnbdbackup -d vm1 -l full -o /tmp/backup_hosta --checkpointdir /mnt/shared/vm1`

 2) After backup, the virtual machine is relocated to host B and loses its
 information about checkpoints and bitmaps, thus, the next full backup
 usually fails with:

```
virtnbdbackup -d vm1 -l full -o /tmp/backup_hostb
[..]
unable to execute QEMU command 'transaction': Bitmap already exists: virtnbdbackup.0
```

 3) Now pass the checkpoint dir and files written from host A, and
 virtnbdbackup will redefine missing checkpoints and execute a new full
 backup. As the new full backup removes all prior checkpoints the bitmap
 information is in sync after this operation and backup succeeds:

```
virtnbdbackup -d vm1 -l full -o /tmp/backup_hostb --checkpointdir /mnt/shared/vm1
[..]
redefineCheckpoints: Redefine missing checkpoint virtnbdbackup.0
[..]
```

See also: https://github.com/abbbi/virtnbdbackup/pull/10

# Supported Hypervisors

`virtnbdbackup` uses the lowest layer on top of libvirt to allow its
functionality, you can also use it with more advanced hypervisors solutions
such as [ovirt](https://www.ovirt.org/), RHEV or OpenNebula, but please bear in
mind that it was not developed to target all of those solutions specifically!

## Ovirt, RHEV or OLVM

If you are using the ovirt node based hypervisor hosts you should consider
creating a virtualenv via the [venv scripts](venv/) and transferring it to the
node system.

On regular centos/alma/rhel based nodes, installation via RPM package should be
preferred. The incremental backup functionality can be enabled via ovirt
management interface.

Usually ovirt restricts access to the libvirt daemon via different
authentication methods. Use the `-U` parameter in order to specify an
authentication file, if you chose to run the utility locally on the
hypervisor:

```
virtnbdbackup -U qemu:///system?authfile=/etc/ovirt-hosted-engine/virsh_auth.conf -d vm1 -o /tmp/backupset/vm1
```

You can also use remote backup functionality:

 * System must be reachable via ssh public key auth as described in the
 [Remote Backup](#remote-backup) section.
 * Some OVIRT based setups may deny SASL based authentication if the hostname
   used to connect to does not match the hostname from the libvirt certificate.
   [more info](https://github.com/abbbi/virtnbdbackup/issues/167#issuecomment-2028467071)
 * Firewall port for NBD must be open:

```
 root@hv-node~# firewall-cmd --zone=public --add-port=10809/tcp
```

and then backup via:

```
virtnbdbackup -U qemu+ssh://root@hv-node/session -d vm -o /backup --password password --user root --ssh-user root
```

`Note:`
> `virtnbdrestore` has not been adopted to cope with the ovirt specific
> domain xml format, so redefining and virtual machine on the node might not
> work.

## OpenNebula

See [past issues](https://github.com/abbbi/virtnbdbackup/issues?q=label%3Aopennebula)

# Authentication

Both `virtnbdbackup` and `virtnbdrestore` commands support authenticating
against libvirtd with the usual URIs. Consider using the following options:

 `-U`: Specify an arbitrary connection URI to use against libvirt

 `--user`: Username to use for the specified connection URI

 `--password`: Password to use for the specified connection URI.

It is also possible to specify the credentials stored as authentication file
like it would be possible using the `virsh -c` option:

```
 -U qemu:///system?authfile=/etc/virsh_auth.conf ..
```

`Note:`
> The default connection URI used is `qemu:///system` which is usually the 
> case if virtual machines operate as root user. Use the `qemu:///session` URI
> to backup virtual machines as regular user.

# Internals
## Backup Format

Currently, there are two output formats implemented:

 * `stream`: the resulting backup image is saved in a streamlined format,
   where the backup file consists of metadata about offsets and lengths
   of zeroed or allocated contents of the virtual machines disk. This is
   the default. The resulting backup image is thin provisioned.
 * `raw`: The resulting backup image will be a full provisioned raw image,
   this should mostly be used for debugging any problems with the extent
   handler, it won't work with incremental backups.

## Extents

In order to save only used data from the images, dirty blocks are queried from
the NBD server. The behavior can be changed by using the option `-q` to use
common qemu tools (nbdinfo). By default `virtnbdbackup` uses a custom
implemented extent handler.

## Backup I/O and performance: scratch files

If virtual domains handle heavy I/O load during backup (such as writing or
deleting lots of data while the backup is active) you might consider using the
`--scratchdir` option to change the default scratch file location.

During the backup operation qemu will use the created scratch files for
fleecing, thus it is recommended to store these files on storage that meets the
same I/O performance requirements as the backup target.

The free space on the default scratch directory (`/var/tmp`) must be enough to
be able to keep all fleecing data while the backup is active.

## Debugging

To get more detailed debug output use `--verbose` option. To enable NBD
specific debugging output export LIBNBD_DEBUG environment variable prior to
executing the backup or restore:

```
export LIBNBD_DEBUG=1
virtnbdbackup [..] --verbose
```

# FAQ
## The thin provisioned backups are bigger than the original qcow images

Virtual machines using the qcow format do compress data. During backup, the
image contents are exposed as NBD device which is a RAW device. The backup data
will be at least as big as the used data within the virtual machine. 

You can use the `--compress` option or other tools to compress the backup
images in order to save storage space or consider using a deduplication capable
target file system.

## Backup fails with "Cannot store dirty bitmaps in qcow2 v2 files"

If the backup fails with error:

```
ERROR [..] internal error: unable to execute QEMU command dirty bitmaps in qcow2 v2 files
```

consider migrating your qcow files to version 3 format. QEMU qcow image version
2 does not support storing advanced bitmap information, as such only backup
mode `copy` is supported.


## Backup fails with "unable to execute QEMU command 'transaction': Bitmap already exists"

During backup `virtnbdbackup` creates a so called "checkpoint" using the
libvirt API. This checkpoint represents an "bitmap" that is saved in the
virtual machines disk image.

If you receive this error during backup, there is an inconsistency between the
checkpoints that the libvirt daemon thinks exist, and the bitmaps that are
stored in the disk image.

This inconsistency can be caused by several situations:

 1) A virtual machine is operated on a cluster and is migrated between host
    systems (See also: [Transient virtual machines: checkpoint persistency on
    clusters](#transient-virtual-machines-checkpoint-persistency-on-clusters))
 2) A change to the libvirt environment between backups (such as re-installing
    the libvirt daemon) caused the system to lose track of the existing
    checkpoints, but the bitmaps are still existent in the disk files.
 3) Between backups, the disk image contents were reset and now the image has
    already defined bitmaps (if disk was restored from a storage snapshot, for
    example )
 4) `virtnbdbackup` is started on an backup target directory with an old state
    and starts from a wrong checkpoint count, now attempting to create an
    checkpoint whose bitmap already exists (might happen if you rotate backup
    directories and pick the wrong target directory with an older state for
    some reason)

To troubleshoot this situation, use virsh to list the checkpoints that libvirt
thinks are existent using:

```
virsh checkpoint-list <domain>
 Name              Creation Time
 ----------------------------------------------
 virtnbdbackup.0   2024-08-01 20:45:44 +0200
```

You can also check which disks were included in the checkpoint:

```
 virsh checkpoint-dumpxml vm1 virtnbdbackup.0 | grep "<disk.*checkpoint="
    <disk name='sda' checkpoint='bitmap' bitmap='virtnbdbackup.0'/>
    <disk name='sdb' checkpoint='no'/>
    <disk name='fda' checkpoint='no'/>
```

The example command shows one existing checkpoint for disk "sda". An bitmap
with the same name should be listed using the `qemu-img` tool for each
checkpoint.

Note:
> Bitmap information is written into the qcow2 metadata only once qemu will
> close the image. As such you need to turn off the virtual machine prior to
> checking the bitmaps.

To list the bitmaps use:

```
virsh destroy vm1       # shutdown vm
virsh domblklist vm1 | grep sda
 sda      /tmp/tmp.Y2PskFFeVv/vm1-sda.qcow2
qemu-img info /tmp/tmp.Y2PskFFeVv/vm1-sda.qcow2
[..]
    bitmaps:
        [0]:
            flags:
                [0]: auto
            name: virtnbdbackup.1
            granularity: 65536
[..]
```

Now, compare which checkpoints are listed and which bitmaps exist in the qcow
image. In this example `virsh` only lists the checkpoint "virtnbdbackup.0" but
the bitmap is called "virtnbdbackup.1", indicating there is an inconsistency.

Remove the dangling bitmap(s) via:

```
  qemu-img bitmap /tmp/tmp.Y2PskFFeVv/vm1-sda.qcow2 --remove virtnbdbackup.1
```

Start with an new full backup to a fresh directory.


## Backup fails with "Bitmap inconsistency detected: please cleanup checkpoints using virsh and execute new full backup"

If an qemu process for a virtual machine is forcefully shutdown after a backup
(for example due to power outage or qemu process killed/crashed) the bitmaps
required for further backups may not have yet been synced to the qcow image.

In these cases, you need to delete the existent checkpoints using:

```
 virsh checkpoint-delete <domain> --checkpointname <checkpoint_name> --metadata
```

and start with a fresh full backup.

`Note`:
> Since version 2.30 virtnbdbackup will handle these situations automatically
> and falls back to a full backup in case it detects a broken bitmap chain.


## Backup fails with "Error during checkpoint removal: [internal error: bitmap 'XX' not found in backing chain of 'XX']"

In this situation the checkpoints are still defined in the libvirt ecosystem
but the required bitmaps in the qcow files do not exist anymore. This is a
situation that is not automatically cleaned up by the backup process because it
may require manual intervention and should usually not happen.

You can cleanup this situation by removing the reported checkpoints via:

```
 virsh checkpoint-delete <domain> --checkpointname <checkpoint_name> --metadata
```

`Note`:
> Since version 2.30 virtnbdbackup will handle these situations automatically
> and falls back to a full backup in case it detects a broken bitmap chain.


## Backup fails with "Virtual machine does not support required backup features, please adjust virtual machine configuration."

The libvirt version you are using does by default not expose the functionality
required for creating full or incremental backups. You can either use the
backup mode `copy` or enable the backup features as described
[here](#libvirt-versions--760-debian-bullseye-ubuntu-20x)

## Backup fails with "Timed out during operation: cannot acquire state change lock"

If backups fail with error:

```
ERROR [..] Timed out during operation: cannot acquire state change lock (held by monitor=remoteDispatchDomainBackupBegin)
```

there is still some block jobs operation active on the running domain, for
example a live migration or another backup job. It may also happen that
`virtnbdbackup` crashes abnormally or is forcibly killed during backup
operation, unable to stop its own backup job.

You can use option `-k` to forcibly kill any running active block jobs for the
domain, but use with care. It is better to check which operation is active with
the `virsh domjobinfo` command first.

```
virtnbdbackup  -d vm2 -l copy -k  -o -
[..]
  INFO virtnbdbackup - main: Stopping domain jobs
```

## Backup fails with "Failed to bind socket to /var/tmp/virtnbdbackup.XX: Permission denied"

The issue is most likely an active `apparmor` profile that prevents the qemu
daemon from creating its socket file for the nbd server. Try to disable
apparmor using the **aa-teardown** command for the current session you are
executing a backup or restore. You can also add the following lines:

```
/var/tmp/virtnbdbackup.* rw,
/var/tmp/backup.* rw,
```

to the configuration files (might not exist by default):

```
/etc/apparmor.d/usr.lib.libvirt.virt-aa-helper
/etc/apparmor.d/local/abstractions/libvirt-qemu
/etc/apparmor.d/local/usr.sbin.libvirtd
```

or, on newer versions:

```
sudo mkdir -p /etc/apparmor.d/abstractions/libvirt-qemu.d
cat <<EOF | sudo tee /etc/apparmor.d/abstractions/libvirt-qemu.d/virtnbdbackup
/var/tmp/virtnbdbackup.* rw,
/var/tmp/backup.* rw,
EOF
sudo service apparmor reload
```

See also: https://github.com/abbbi/virtnbdbackup/issues/7

## High memory usage during backup

libnbd python implementation has had various memory leaks in older versions
which cause such problems.

For centos 8 based distributions these fixes have been backported to libnbd
`1.4.0.`

The fix itself was released with libnbd 1.5.2, so be sure to use at least this
version if using `virtnbdbackup` on any other distribution.

See also: https://github.com/abbbi/virtnbdbackup/issues/8

## fstrim and (incremental) backup sizes

If virtual machines have configured disks with discard option and fstrim is
running frequently, trimmed blocks are detected during backup operation by
default.

If, for example, the fstrim operation frees 30 GiB of disk space, and the
virtual machine has only 5 GiB of changed data blocks, 30 GiB of data
will be skipped during incremental backup.

This works by comparing the complete allocation bitmap of the virtual machine
disk images during incremental backup.

Behavior can be disabled, if desired, using the `--no-sparse-detection` option.


## Test your backups!

The utility is provided "as is", i take no responsibility or warranty if you
face any issues recovering your data! The only way to ensure your backups are
valid and your backup plan works correctly is to repeatedly test the integrity
by restoring them! If you discover any issues, please do not hesitate to report
them.

## Links

Backup howto for Debian Bullseye: https://abbbi.github.io/debian/

Short video: https://youtu.be/dOE0iB-CEGM
