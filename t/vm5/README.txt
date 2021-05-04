Qcow image has bitmap "virtnbdbackup" set using

   qemu-img bitmap --add vm5-sda.qcow2 virtnbdbackup

backup of virtual machine  fails with:

 ERROR virtnbdbackup - main: internal error: unable to execute QEMU command 'transaction': Bitmap already exists: virtnbdbackup

because libvirt does not know about the bitmap set
in the qcow file.
