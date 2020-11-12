# virtnbdbackup

Just a simple sample how backing up virtual machine disk via NBD,
using libnbd to query block status and only save used data within
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
usage: virtnbdbackup.py [-h] [-t {stream,raw}] [-q]

Backup

optional arguments:
  -h, --help            show this help message and exit
  -t {stream,raw}, --type {stream,raw}
                        Output type: stream or raw
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
  backup XML:
  
  virsh backup-begin --backupxml backup.xml --domain XX

* Now the libvirt process has created an NBD server handle
  which can be used to backup the data.
  
  To create a full provisioned backup run:
  
  virtnbdbackup --type raw
  
  The resulting image can be mounted via kpartx, for example:
  
  ```
   kpartx -av sda.data 
    add map loop1p1 (253:5): 0 7811072 linear 7:1 2048
    add map loop1p2 (253:6): 0 55101440 linear 7:1 7813120
  ```
  
# TODO

 * implement complete VM backup via libvirt
 * implement restore :-)
