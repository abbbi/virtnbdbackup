# virtnbdbackup

Backup utility for libvirt, using latest CBT features.
Work in progress ..

# Prerequisites

* libvirt 6.x from the centos8 advanced virtualization stream
* Virtual machine must enable incremental backup feature by
  including following statement in its configuration:
 
 ```
  <domain type='kvm' id='1' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
    <qemu:capabilities>
    <qemu:add capability='incremental-backup'/>
  </qemu:capabilities
 ```
 
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
 
# Extents

In order to save only used data from the images, extent information is queried
from the NBD server. This happens by either using the qemu tools (qemu-img map
..) if option "-q" is specified, or by an custom implemented extent handler.

# Backup Operation

Following backup modes can be used:

* copy: Full backup of virtual machine, no checkpoint is created for further
  incremental backups, existing checkpoints will be left.

* full: Full backup of virtual machine, but a checkpoint named `virnbdbackup'
  will be created, all existant checkpoints including this name will be
  removed: a new backup chain is created

* inc: Perform incremental backup, based on the last checkpoint, checkpoints
  are tracked.

All required informations for restore are saved within the same directory,
including the virtual machine configuration, checkpoint information and disk
data.

The target directory should be rotead if a new backup set is created, as for
each backup chain a new directory is mandatory.

# Backup Examples

* Start full backup of domain "cbt":

```
 virtnbdbackup -d cbt -l full -o /tmp/backupset
```

* Start incremental backup for domain "cbt":

```
 virtnbdbackup -d cbt -l full -o /tmp/backupset
```

# Restore examples

For restoring, ```virtnbdrestore```` can be used. It processes the streamed
backup format back into a usable qemu qcow image. Option ```--until````
allows to perform a point in time restore up to a desired checkpoint.

As a first start, the ```dump```` parameter can be used to dump the saveset
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

Restoring all disks within the backupset into an usable qcow image via:

```
virtnbdrestore -i /tmp/backupset/ -a restore -o /tmp/restore
```

# TODO

 * Call filesystem freeze/thaw before starting backup session
