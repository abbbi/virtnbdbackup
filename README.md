![ci](https://github.com/abbbi/virtnbdbackup/actions/workflows/ci-ubuntu-latest.yml/badge.svg)

# virtnbdbackup

Backup utility for `libvirt`, using the latest changed block tracking features.
Create online, thin provisioned full and incremental or differencial backups
of your `kvm/qemu` virtual machines.

![Alt text](screenshot.jpg?raw=true "Title")

# 

* [About](#about)
* [Prerequisites/Requirements](#prerequisites)
* [Installation](#installation)
   * [Python package](#python-package)
   * [RPM package](#rpm-package)
      * [Redhat/Centos/Alma](#centosalmalinux-8)
   * [Debian package](#debian-package)
   * [Vagrant](#vagrant)
   * [Venv](#virtualenv)
   * [Docker images](#docker-images)
* [Backup Format](#backup-format)
* [Backup Operation](#backup-operation)
* [Backup concurrency](#backup-concurrency)
* [Supported disk formats / raw disks](#supported-disk-formats--raw-disks)
* [Backup Examples](#backup-examples)
   * [Excluding disks](#excluding-disks)
   * [Estimating backup size](#estimating-backup-size)
   * [Compression](#compression)
   * [Pipe data to other hosts](#pipe-data-to-other-hosts)
* [Kernel/initrd and additional files](#kernelinitrd-and-additional-files)
* [Restore examples](#restore-examples)
   * [Dumping backup information](#dumping-backup-information)
   * [Complete restore](#complete-restore)
   * [Process only specific disks during restore](#process-only-specific-disks-during-restore)
   * [Point in time recovery](#point-in-time-recovery)
   * [Single file restore and instant recovery](#single-file-restore-and-instant-recovery)
* [Extents](#extents)
* [Transient virtual machines: checkpoint persistency](#transient-virtual-machines-checkpoint-persistency)
* [FAQ](#faq)
   * [The thin provisioned backups are bigger than the original qcow images](#the-thin-provisioned-backups-are-bigger-than-the-original-qcow-images)
   * [Is the backup application consistent?](#is-the-backup-application-consistent)
   * [Backup fails with "Cannot store dirty bitmaps in qcow2 v2 files"](#backup-fails-with-cannot-store-dirty-bitmaps-in-qcow2-v2-files)
   * [Backup fails with "Timed out during operation: cannot acquire state change lock"](#backup-fails-with-timed-out-during-operation-cannot-acquire-state-change-lock)
   * [Backup fails with "Failed to bind socket to /var/tmp/virtnbdbackup.XX: Permission denied"](#backup-fails-with-failed-to-bind-socket-to-vartmpvirtnbdbackupxx-permission-denied)
   * [High memory usage during backup](#high-memory-usage-during-backup)
* [Links](#links)
* [Test your backups!](#test-your-backups)

# About

Existing backup solutions or scripts for `libvirt/kvm` usually depend on the
external snapshot feature to create backups, sometimes even require to
shutdown or pause the virtual machine.

Recent additions to both the `libvirt` and `qemu` projects have introduced new
capabilities that allow to create online (full and incremental) backups, by
using so called `dirty bitmaps` (or changed block tracking).

`virtnbdbackup` uses these features to create online full and incremental
or differencial backups.

`virtnbdrestore` can be used to re-construct the complete image from the
thin provisioned backups.

`virtnbdmap` can be used to map an thin provisioned backup image into a
block device on-the-fly, for easy single file restore or even instant
boot from an backup image.

For backing up standlone qemu virtual machines not managed by libvirt, see this
project: https://github.com/abbbi/qmpbackup

# Prerequisites

* Obviously a libvirt/qemu version that supports the incremental backup
  features.

  On Centos8/Almalinux, libvirt packages from the advanced virtualization
  stream support all required features. To install libvirt from the stream use:

  ```
  yum install centos-release-advanced-virtualization
  yum makecache
  yum module install virt
  ```

  Debian bullseye or Ubuntu 20.x include libvirt versions supporting this
  feature already.

* Virtual machines running on libvirt versions < 8.2.0 **must enable
  incremental backup feature** by including the capability statement and using
  the extended schema (the first line must be changed, too) in its
  configuration as shown below:

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
> It is mandatory to restart the virtual machine once you have altered
> its configuration to make the featureset available.
 
 * python libvirt module version  >= 6.0.0 (yum install python3-libvirt)
 * python libnbd bindings (https://github.com/libguestfs/libnbd) version >= `1.5.5` (yum install python3-libnbd)
 * The virtual machine should use qcow version 3 images to support the full feature set.
 
# Installation
## Python package
```
python3 setup.py install
```

## RPM package

To create an RPM package from source suitable for installation:

### Centos/Almalinux 8

To build the rpm package from source:

```
yum install epel-release    # required for tqdm on centos 8
yum makecache
yum install rpm-build
python3 setup.py bdist_rpm
yum install dist/virtnbdbackup-<version>-.noarch.rpm
```

## Debian package

To create a Debian package (Debian bullseye required) use:

```
sudo apt-get install python3-all python3-stdeb dh-python python3-libnbd python3-tqdm python3-lz4
python3 setup.py --command-packages=stdeb.command bdist_deb
```

## Vagrant

You can also use existing [vagrant scripts](vagrant/) to build the packages.

## Virtualenv

For setup within an virtualenv see [venv scripts](venv/).

## Docker images

See: https://github.com/adrianparilli/virtnbdbackup-docker

# Backup Format

Currently, there are two output formats implemented:

 * `stream`: the resulting backup image is saved in a streamlined format,
   where the backup file consists of metadata about offsets and lengths
   of zeroed or allocated contents of the virtual machines disk. This is
   the default. The resulting backup image is thin provisioned.
 * `raw`: The resulting backup image will be a full provisioned raw image,
   this should mostly be used for debugging any problems with the extent
   handler, it won't work with incremental backups.

# Backup Operation

Following backup modes can be used:

* `copy`: Full, thin provisioned backup of the virtual machine disks, no
  checkpoint is created for further incremental backups, existing checkpoints
  will be left untouched. This is the default mode and works with qcow images
  not supporting persistent bitmaps.

* `full`: Full, thin provisioned backup of the virtual machine, a new checkpoint
  named `virtnbdbackup` will be created, all existent checkpoints from prior
  backups matching this name will be removed: a new backup chain is created.

* `inc`: Perform incremental backup, based on the last full or incremental
  backup. A checkpoint for each incremental backup is created and saved.

* `diff`: Perform differencial backup: saves the current delta to the last
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

`Note`:
> If the virtual domain is not in running state (powered off) `virtnbdbackup` 
> supports both `copy` and `inc` backup modes. Incremental backups will then 
> save the changed blocks of the last existing checkpoint. As no new checkpoints
> can be defined for offline domains, the Backup mode `full` is changed to mode
> `copy`.

It is possible to backup multiple virtual machines on the same host system at
the same time, using separate calls to the application with a different target
directory to store the data.

# Supported disk formats / raw disks

`libvirt/qemu` supports dirty bitmaps, required for incremental backups only
with qcow(v3) based disk images. If you are using older image versions, you can
only create `copy` backups, or consider converting the images to a newer
format using `qemu-img`.

By default `virtnbdbackup` will exclude all disks with format `raw`. This
behavior can be changed if option  `--raw` is specified, raw disks will then be
included during a `full` backup. This of course means that no thin provisioned
backup is created for these particular disks.

During restore, these files can be copied "as is" from the backup folder and
must not be processed using `virtnbdrestore`.

# Backup Examples

* Start full backup of domain `vm1`, save data to `/tmp/backupset`:

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset
```

* Start incremental backup for domain `vm1`, backup only changed blocks to the
  last full backup:

```
virtnbdbackup -d vm1 -l inc -o /tmp/backupset
```

The resulting directory will contain all information for restoring the virtual
machine, including logfiles that can be used for analyzing backup issues:

```
/tmp/backupset/
├── backup.full.05102021161752.log
├── backup.inc.05102021161813.log
├── backup.inc.05102021161814.log
├── checkpoints
│   ├── virtnbdbackup.0.xml
│   ├── virtnbdbackup.1.xml
│   └── virtnbdbackup.2.xml
├── sda.full.data
├── sda.inc.virtnbdbackup.1.data
├── sda.inc.virtnbdbackup.2.data
├── vm1.cpt
├── vmconfig.virtnbdbackup.0.xml
├── vmconfig.virtnbdbackup.1.xml
└── vmconfig.virtnbdbackup.2.xml
```

## Excluding disks

Option `-x` can be used to exclude certain disks from the backup. The name of
the disk to be excluded must match the disks target device name as configured
in the domains xml definition, for example:

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset -x sda
```

Special devices such as `cdrom/floppy` or `direct attached luns` are excluded
by default, as they are not supported by the changed block tracking layer.

It is also possible to only backup specific disks using the include option
(`--include`, or `-i`):

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset -i sdf
```

## Estimating backup size

Sometimes it can be useful to estimate the data size prior to executing the
next `full` or `copy` backup. This can be done by using the option `-p` which will
query the virtual machine extents and provides a summary about the size
of the changed extents:

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset -p
[..]
2021-03-29 11:32:03 INFO virtnbdbackup - backupDisk: Got 866 extents
2021-03-29 11:32:03 INFO virtnbdbackup - backupDisk: 2147483648 bytes disk size
2021-03-29 11:32:03 INFO virtnbdbackup - backupDisk: 1394147328 bytes of data extents to backup
```

# Backup concurrency

If `virtnbdbackup` saves data to a regular target directory, it starts one
thread for each disk it detects to speed up the backup operation.

This behavior can be changed using the `--worker` option to define an amount of
threads to be used for backup. Depending on how many disks your virtual machine
has attached, it might make sense to try a different amount of workers to see
which amount your hardware can handle best.

If standard output (`-`) is defined as backup target, the amount of workers is
allways limited to 1, to ensure a valid Zip file format.

## Compression

It is possible to enable compression for the `stream` format via `lz4`
algorithm by using the `--compress` option. The saved data is compressed inline
and the saveset file is appended with compression trailer including information
about the compressed block offsets.

During the restore, `virtnbdrestore` will automatically detect such compressed
backup streams and attempts to decompress saved blocks accordingly.

Using compression will come with some CPU overhead, both lz4 checksums for
block and original data are enabled.

## Pipe data to other hosts

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
saved to the backup folder aswell.

As the virtual domain might depend on certain UEFI settings or vars to
correctly boot, you must take care to copy these files to your restore target
manually.

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
information of an existing backupset:

```
virtnbdrestore -i /tmp/backupset/ -a dump -o /tmp/restore 
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

## Complete restore

To restore all disks within the backupset into a usable qcow image use
command:

```
virtnbdrestore -i /tmp/backupset/ -a restore -o /tmp/restore
```

All incremental backups found will be applied to the target images
in the output directory `/tmp/restore`

`Note`:
> The restore utility will copy the latest virtual machine config to the
> target directory, but wont alter its contents. You have to adjust the config
> file for the new pathes and/or excluded disks to be able to define and run it.

## Process only specific disks during restore

A single disk can be restored by using the option `-d`, the disk name has
to match the virtual disks target name, for example:

```
virtnbdrestore -i /tmp/backupset/ -a restore -o /tmp/restore -d sda
```

## Point in time recovery

Option `--until` allows to perform a point in time restore up to the desired
checkpoint. The checkpoint name has to be specified as reported by the
dump output (field `checkpointName`), for example:

```
virtnbdrestore -i /tmp/backupset/ -a restore -o /tmp/restore --until virtnbdbackup.2
```

It is also possible to specify the source data files specifically used for the
rollback via `--sequence` option, but beware: you must be sure the sequence you
apply has the right order, otherwise the restored image might be errnous,
example:

```
virtnbdrestore -i /tmp/backupset/ -a restore -o /tmp/restore --sequence vdb.full.data,vdb.inc.virtnbdbackup.1.data
```

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
 # virtnbdmap -f /backup/sda.full.data
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
virtnbdmap -f /backup/sda.full.data,/backup/sda.inc.virtnbdbackup.1.data,/backup/sda.inc.virtnbdbackup.2.data
[..]
[..] INFO virtnbdmap - main [MainThread]: Need to replay incremental backups
[..] INFO virtnbdmap - main [MainThread]: Replaying offset 420 from /backup/sda.inc.virtnbdbackup.1.data
[..] INFO virtnbdmap - main [MainThread]: Replaying offset 131534 from /backup/sda.inc.virtnbdbackup.1.data
[..] INFO virtnbdmap - <module> [MainThread]: Done mapping backup image to [/dev/nbd0]
[..] INFO virtnbdmap - <module> [MainThread]: Press CTRL+C to disconnect
[..]
```

The original image will be left untouched as nbdkits copy on write filter is
used to replay the changes.

You also create an overlay image via `qemu-img` and boot from it right away:

```
qemu-img create -b /dev/nbd0 -f qcow2 bootme.qcow2
qemu-system-x86_64 -enable-kvm -m 2000 -hda bootme.qcow2
```

To remove the mappings, stop the utility via "CTRL-C"

`Note`:
> If you attempt to mount the filesystems mapped, you may need to add several
> mount options (XFS for example needs `-o norecovery,ro`). Additionally, if
> the backed up virtual machine has logical volumes which have the same name
> then the system you are mapping the diks to, you need to activate them
> forcefully to be able to access them correctly.

# Extents

In order to save only used data from the images, dirty blocks are queried from
the NBD server. The behavior can be changed by using the option `-q` to use
common qemu tools (nbdinfo). By default `virtnbdbackup` uses a custom
implemented extent handler.

# Transient virtual machines: checkpoint persistency

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

# FAQ
## The thin provisioned backups are bigger than the original qcow images

Virtual machines using the qcow format do compress data. During backup, the
image contents are exposed as NDB device which is a RAW device. The backup data
will be at least as big as the used data within the virtual machine. 

You can use the `--compress` option or other tools to compress the backup
images in order to save storage space or consider using a deduplication capable
target file system.

## Is the backup application consistent?

During backup `virtnbdbackup` attempts to freeze the file systems within the
domain using the qemu guest agent filesystem freeze and thaw functions.  In
case no qemu agent is installed or filesystem freeze fails, a warning is issued
during backup:

```
WARNING [..] Guest agent is not responding: QEMU guest agent is not connected
```

In case you receive this warning, check if the qemu agent is installed and
running with in the domain.

`Note:`
> It is highly recommended to have an qemu agent running within the virtual
> domain to have a consistent file system during backup!

## Backup fails with "Cannot store dirty bitmaps in qcow2 v2 files"

If the backup fails with error:

```
ERROR [..] internal error: unable to execute QEMU command dirty bitmaps in qcow2 v2 files
```

consider migrating your qcow files to version 3 format. QEMU qcow image version
2 does not support storing advanced bitmap information, as such only backup
mode `copy` is supported.

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

See also: https://github.com/abbbi/virtnbdbackup/issues/7

## High memory usage during backup

libnbd python implementation has had various memory leaks in older versions
which cause such problems.

For centos 8 based distributions these fixes have been backported to libnbd
`1.4.0.`

The fix itself was released with libnbd 1.5.2, so be sure to use at least this
version if using `virtnbdbackup` on any other distribution.

See also: https://github.com/abbbi/virtnbdbackup/issues/8

## Test your backups!

The utility is provided "as is", i take no responsibility or warranty if you
face any issues recovering your data! The only way to ensure your backups are
valid and your backup plan works correctly is to repeatedly test the integrity
by restoring them! If you discover any issues, please do not hesitate to open
an issue.

## Links

Backup howto for Debian Bullseye: https://abbbi.github.io/debian/

Short video: https://youtu.be/dOE0iB-CEGM
