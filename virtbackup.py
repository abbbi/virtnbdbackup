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

writer = open('backup.data','wb')
metadata = sparsestream.SparseStream().dump_metadata("0", "", "none", "vda", False)
sparsestream.SparseStream().write_frame(writer, sparsestream.SparseStreamTypes().META, 0, len(metadata))
writer.write(metadata)
writer.write(sparsestream.SparseStreamTypes().TERM)
print("got %s extents" % len(extents))

for save in extents:
    if save.data == True:
        print("read %s from %s" %(save.length, save.offset))
        sparsestream.SparseStream().write_frame(writer, sparsestream.SparseStreamTypes().DATA, save.offset, save.length)
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
                writer.write(data)
                offset+=bs
        else:
            data = h.pread(save.length, save.offset)
            writer.write(data)
        writer.write(sparsestream.SparseStreamTypes().TERM)
    else:
        print("skip %s from %s" %(save.length, save.offset))
        sparsestream.SparseStream().write_frame(writer, sparsestream.SparseStreamTypes().ZERO, save.offset, save.length)

sparsestream.SparseStream().write_frame(writer, sparsestream.SparseStreamTypes().STOP, 0, 0)
writer.close()
