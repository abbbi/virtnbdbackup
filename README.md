# virtnbdbackup

Just a simple sample showing how to backup a libvirt virtual machine disk
via NBD, using libnbd to query its block status and only save used data within
disk image. Work in progress, many features yet to be implemented.

# prerequisites

* libvirt 6.x from the centos8 advanced virtualization stream
* Virtual machine must enable incremental backup feature by
  including following statement in its configuration:
 
 ```
  <domain type='kvm' id='1' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
    <qemu:capabilities>
    <qemu:add capability='incremental-backup'/>
  </qemu:capabilities
 ```
 
# Help
```
usage: virtnbdbackup [-h] [-t {stream,raw}] -f FILE [-q]

Backup

optional arguments:
  -h, --help            show this help message and exit
  -t {stream,raw}, --type {stream,raw}
                        Output type: stream or raw
  -f FILE, --file FILE  Output target file
  -d DOMAIN, --domain DOMAIN
                        Domain to backup
  -q, --qemu            Use Qemu tools to query extents
```

# Backup Format

Currently there are two methods implemented:

 * raw: The resulting backup image will be a full provisioned raw image
 * stream: the resulting backup image is saved in a streamlined format
 
# Extents

In order to save only used data from the images, extent information is queried
from the NBD server. This happens by either using the qemu tools (qemu-img map
..) if option "-q" is specified, or by an custom implemented extent handler.


# Backup Examples

* Start backup of virtual machine, to create a full provisioned raw
  backup for all disks, run the following command:
  
  ```
  virtnbdbackup -t raw -f /tmp/prefix -d DOMAIN_NAME
  ```
  
  The resulting image(s) can be mounted via kpartx, for example:
  
  ```
   kpartx -av /tmp/prefix.sda.data
    add map loop1p1 (253:5): 0 7811072 linear 7:1 2048
    add map loop1p2 (253:6): 0 55101440 linear 7:1 7813120
  ```
  
* Backup only one disk in streaming mode to stdout, compress data on the
  fly:

  ```
  virtnbdbackup  -t stream -d cbt -i sda  -f - | gzip -v9 > data
  ```

* Have some throughput using "p":

  ```
  virtnbdbackup  -t stream -d cbt -i sda  -f - | pv > /tmp/data
  ```

* Starting a full backup will create an checkpoint:
  ```
   virtnbdbackup -l full -t stream -d cbt  -f /tmp/prefix
  ```

* After creating a full backup, a incremental backup can be created:

  ```
   virtnbdbackup -l inc -t stream -d cbt  -f /tmp/prefix
  ```

# Restore examples

In order to restore the regular raw images one can use qemu-img convert
and simply convert them into a qcow2 image or write them to an nbd mapped
qcow file.

For the stream format, restorestream can be used, the workflow is as
follows:

 * create a file with the same size as original:
    ```
    `qemu-img create -f qcow2 /tmp/RESTORE.qcow2 30G`
    ```
* Attach an qemu-nbd process to it:
    ```
    qemu-nbd -x vda -f qcow2 /tmp/RESTORE.qcow2
    ```
* Restore the data via:
    ```
    restorestream < /tmp/BACKUP.sda.data
    ```


# TODO

 * Call filesystem freeze/thaw before starting backup session
 * implement incremental backup via checkpoints
 * implement restore :-)
