This test uses the arch Linux cloud image to create multiple backups with
different actions in between.

The image includes an Qemu agent that is used to alter data within the virtual
machine while it is active. Actions between incremental backups involve:

 * alter some data by copying /etc to different target directory
 * fstrim
 * create some folders
 * delete some data
 * fstrim again
 * create ~500 MB file and store checksum
 * restore disk image and check contents
 * boot virtual machine
 * verify checksum of created data file within booted VM

Also, the image responds very well to fstrim, attempting to trim about 38 GB of
data right from the start, which makes it perfect to test against the dirty
zero regions during backup.

Restore attempts to boot virtual machine and also checks restored data for
existence and verifies checksums.
