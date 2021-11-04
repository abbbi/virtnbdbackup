# Instant recovery

These tools can be used to map thin provisioned full backups (stream format)
into usable block devices. This enables users to restore single files without
having to reconstruct the complete disk image.

It should be considered a proof of concept. The following example shows how to
use the utilities to extract a single file from a existing full backup.

The backup used for this example is a full backup with a running Linux
instance, having its root file system on XFS/LVM.

* [Howto](#howto)
    * [Prerequisites](#prerequisites)
    * [Create the block map](#create-the-block-map)
    * [Start the NBD backend using nbdkit](#start-the-nbd-backend-using-nbdkit)
    * [Map the NBD endpoint to a device](#map-the-nbd-endpoint-to-a-device)
    * [Accessing the data](#accessing-the-data)

# Prerequisites

The following utilities are required:

 * nbdkit  (with python plugin and blockfilter plugin)
 * qemu-nbd
 * The nbd kernel module, loaded via:
 
```
 # modprobe nbd max_partitions=10
```

# Create the block map

As first step we need to dump a list of block offsets from the existing
full backup. You can use the `dumpstream` utility to do so.

```
  # ./dumpstream -d /tmp/BACKUP/vda.full.data > blocks.json
```

The command creates a json formatted file which includes information
about the original an logical data and zeroed regions.

# Start the NBD backend using nbdkit

As a next step, we need to create an NBD Server backend which we can
connect to a block device. This is done via nbdkit, which needs the
following mandatory parameters:

 * the path to the sparsestream plugin
 * the blockmap (`block.json`) we just created
 * the path to the full backup file
 * a block size limit (4096 is known to work)
 
```
# nbdkit --filter=blocksize -f -v python ./sparsestream blockmap=blocks.json disk=/tmp/BACKUP/vda.full.data -t 1 maxlen=4096
```

This command will start in the foreground and create a usable NBD TCP endpoint
on `127.0.0.1:10809`. Leave it running and continue in another terminal
session.

# Map the NBD endpoint to a device

Next, create an nbd mapping with the following command:

```
 qemu-nbd -c /dev/nbd0 nbd://127.0.0.1:10809/sda -r
```

The contents of the virtual disk image are now exposed as `/dev/nbd0`

# Accessing the data

You can now access the device `/dev/nbd0` like any regular disk device:

```
# fdisk -l /dev/nbd0
Disk /dev/nbd5: 37 GiB, 39728447488 bytes, 77594624 sectors
[..]
Device      Boot   Start      End  Sectors  Size Id Type
/dev/nbd5p1 *       2048  1026047  1024000  500M 83 Linux
/dev/nbd5p2      1026048 77594623 76568576 36.5G 8e Linux LVM
```

In this example, we need to check on the LVM volumes and mount
the XFS file system like so:

```
  # vgchange --refresh
  # vgs
  VG       #PV #LV #SN Attr   VSize   VFree
  system-vg   1   3   0 wz--n- 475.96g 2.34g
  vg_main    1   2   0 wz--n- <36.51g    0   < volume from the backup

```

The fileystem can then be mounted (here, norecovery,ro and nouuid
are mandatory because the vm backed up was not running qemu agent
to have a consistent XFS file system within the backup and recovery 
wont work with a read only device).

```
  # mount /dev/vg_main/lv_root /mnt -o norecovery,ro,nouuid
  # tail /mnt/etc/passwd
  systemd-coredump:x:999:997:systemd Core Dumper:/:/sbin/nologin
  systemd-resolve:x:193:193:systemd Resolver:/:/sbin/nologin
```


# Cleanup

To disconnect everything:

```
 # umount /mnt
 # qemu-nbd -d /dev/nbd0
```

And stop the nbdkit process.
