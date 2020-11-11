== virtnbdbackup ==

Just a simple sample how backing up virtual machine disk via NBD,
using libnbd to query block status and only save used data within
disk image.

== prerequisites ==

* libvirt 6.x from the centos8 advanced virtualization stream
* Virtual machine must enable incremental backup feature by
  including following statement in its configuration:
 
 ``
  <domain type='kvm' id='1' xmlns:qemu='http://libvirt.org/schemas/domain/qemu/1.0'>
    <qemu:capabilities>
    <qemu:add capability='incremental-backup'/>
  </qemu:capabilities
 ``
 
== Workflow ==

* Start backup of virtual machine via virsh and a defined
  backup XML:
  
  virsh backup-begin --backupxml backup.xml --domain XX

* Execute virtbackup.py, data is saved to local file
