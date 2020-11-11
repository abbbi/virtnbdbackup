import nbd
import extenthandler
import sparsestream
import sys

h = nbd.NBD()
h.add_meta_context("base:allocation")
h.set_export_name("sda")
h.connect_tcp('localhost','10809')

extentHandler = extenthandler.ExtentHandler(h)

extents = extentHandler.queryBlockStatus()

writer = open('rawbackup.data','wb')
writer.truncate(h.get_size())
print("got %s extents" % len(extents))

# crate raw backup file, just like
#  qemu-img convert -f raw nbd://localhost:10809/sda <file> would do
for save in extents:
    if save.data == True:
        if save.length >= 33554432:
            print("bigger")
            assert save.length % 65536 == 0
            bs = 65536
            offset = save.offset
            count = int(save.length/bs)
            ct = 1
            while ct <= count:
                data = h.pread(bs, offset)
                ct+=1
                writer.seek(offset)
                writer.write(data)
                offset+=bs
        else:
            writer.seek(save.offset)
            data = h.pread(save.length, save.offset)
            writer.write(data)
    else:
        writer.seek(save.offset)

writer.close()
