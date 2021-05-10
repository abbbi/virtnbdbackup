Qcow image has bitmap "virtnbdbackup" set using

   qemu-img bitmap --add vm5-sda.qcow2 virtnbdbackup.0

backup of virtual machine  fails with:

 ERROR virtnbdbackup - main: internal error: unable to execute QEMU command 'transaction': Bitmap already exists: virtnbdbackup.0

because libvirt does not know about the bitmap set
in the qcow file.
