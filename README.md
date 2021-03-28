# virtnbdbackup

Backup utility for libvirt, using latest CBT features. Create full and incremental backups of your virtual machines.

# Prerequisites

* Obviously an libvirt/qemu version that supports the incremental backup
  features. (libvirt 6.x from the centos8 advanced virtualization stream does
  come with required features). To install libvirt from the stream use:

  ```
  yum install centos-release-advanced-virtualization
  yum update
  yum module install virt
  ```

* Virtual machine must enable incremental backup feature by
  including the capabilitys statement and using the extended schema 
  in its configuration as shown below:
 
 ```
  <domain type='kvm' id='1' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
  [..]
  <qemu:capabilities>
    <qemu:add capability='incremental-backup'/>
  </qemu:capabilities
  [..]
  </domain>
 ```
 
 * python libvirt module version  >= 6.0.0 (yum install python3-libvirt)
 * python libnbd bindings (https://github.com/libguestfs/libnbd) version >= 1.5.5 (yum install python3-libnbd)

# Backup Format

Currently there are two output formats implemented:

 * stream: the resulting backup image is saved in a streamlined format,
   where the backup stream consists of meta data about offsets and lengths
   of zeroed or allocated contents of the virtual machines disk.
 * raw: The resulting backup image will be a full provisioned raw image,
   this should mostly be used for debugging any problems with the extent
   handler, it wont work with incremental backups.
   
# Execution

Currently the required components have to be installed and executed on the
libvirt host itself, remote connections are possible and are subject to
further releases.

# Backup Operation

Following backup modes can be used:

* copy: Full backup of virtual machine, no checkpoint is created for further
  incremental backups, existing checkpoints will be left.

* full: Full backup of virtual machine, a new checkpoint named `virtnbdbackup'
  will be created, all existant checkpoints from prior backups including this name
  will be removed: a new backup chain is created.

* inc: Perform incremental backup, based on the last full or incremental backup.

All required informations for restore are saved within the same directory,
including the virtual machine configuration, checkpoint information and disk
data.

The target directory must be rotated if a new backup set is created.

# Backup Examples

* Start full backup of domain "cbt":

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset
```

* Start incremental backup for domain "cbt":

```
virtnbdbackup -d vm1 -l inc -o /tmp/backupset
```

The resulting directory will contain all information for restoring the virtual
machine, including logfiles that can be used for analyzing backup issues:

```
/tmp/backupset/
├── backup.full.03272021122832.log
├── backup.inc.03272021122906.log
├── sda.full.data
├── sda.inc.virtnbdbackup.2.data
├── vm1.cpt
├── vmconfig.virtnbdbackup.2.xml
└── vmconfig.virtnbdbackup.xml
```

## Excluding disks

Option `-x` can be used to exclude certain disks from the backup. The name of
the disk to be excluded must match the disks target device name as configured
in the domains xml definition, for example:

```
virtnbdbackup -d vm1 -l full -o /tmp/backupset -x sda
```

# Restore examples

For restoring, `virtnbdrestore` can be used. It processes the streamed backup
format back into a usable qemu qcow image. Option `--until` allows to perform a
point in time restore up to a desired checkpoint.

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
 'stream-version': 1,
 'virtualSize': 32212254720}
[..]
```

To restore all data within the backupset into an usable qcow image use
command:

```
virtnbdrestore -i /tmp/backupset/ -a restore -o /tmp/restore
```

The restore will create an qcow image that has all changes applied and can be
mounted or attached to a running virtual machine to recover required files.

# Extents

In order to save only used data from the images, dirty blocks are queried from
the NBD server. The behavior can be changed by using option `-q` to use common
qemu tools (qemu-img map ..). By default `virtnbdbackup` uses a custom
implemented extent handler.

# FAQ
## The thin provisioned backups are bigger than the original qcow images

Virtual machines using the QCOW format do compress data. During backup, the image
contents are exposed as NDB device which is a RAW device, as such, the backup data
is as least as big as the used data within the virtual machine. Use xz or tar to
compress the backup images in order to save storage space.

## Is the backup application consistent?

During backup `virtnbdbackup` attempts to freeze the file systems within the
domain using the qemu guest agent filesystem freeze and thaw functions.  In
case no qemu agent is installed or filesytem freeze fails, an warning is issued
during backup:

```
WARNING [..] Guest agent is not responding: QEMU guest agent is not connected
```

In case you receive this warning, check if the qemu agent is installed and
running with in the domain.

## Backup fails with "Cannot store dirty bitmaps in qcow2 v2 files"

In case the backup fails with error:

```
ERROR [..] internal error: unable to execute QEMU command dirty bitmaps in qcow2 v2 files
```

consider migrating your qcow files to version 3 format. QEMU QCOW Image version
2 does not support storing advanced bitmap informations, as such only backup mode
`copy` is supported.

## Backup fails with "Timed out during operation: cannot qcquire state change lock"

If backups fail with error:

```
ERROR [..] Timed out during operation: cannot acquire state change lock (held by monitor=remoteDispatchDomainBackupBegin)
```

there is still some backup operation active on the running domain. This may happen
if `virtnbdbackup` crashes abnormally or is forcibly killed during backup operation,
or simply if another application is currently executing an active backup job.

You can use option `-k` to forcibly kill any running active backup jobs for the
domain:

```
virtnbdbackup  -d vm2 -l copy -k  -o -
[..]
  INFO virtnbdbackup - main: Stopping domain jobs
```

# TODO

 * Allow remote backup
