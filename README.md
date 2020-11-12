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

 
# Workflow

* Start backup of virtual machine via virsh and a defined
  To create a full provisioned backup raw run:
  
  ```
  virtnbdbackup -t raw -f /tmp/backup.data -d DOMAIN_NAME
  ```
  
  The resulting image can be mounted via kpartx, for example:
  
  ```
   kpartx -av /tmp/backup.data
    add map loop1p1 (253:5): 0 7811072 linear 7:1 2048
    add map loop1p2 (253:6): 0 55101440 linear 7:1 7813120
  ```
  
# TODO

 * Call filesystem freeze/thaw before starting backup session
 * implement restore :-)
