#!/usr/bin/env python3
import argparse
import nbdhelper
import extenthandler
import sparsestream
import qemuhelper
import logging
import sys

def main():
    logging.getLogger("sh").setLevel(logging.WARNING)
    logger = logging
    logger.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='Backup')
    parser.add_argument("-t", "--type", default="stream",
        choices=['stream','raw'],
        type=str,
        help="Output type: stream or raw")
    parser.add_argument("-f", "--file", required=True,
        type=str,
        help="Output target file")
    parser.add_argument("-q", "--qemu", default=False,
        help="Use Qemu tools to query extents",
        action="store_true")
    try:
        args = parser.parse_args()
    except:
        parser.print_help()
        sys.exit(1)

    nbdClient = nbdhelper.nbdClient('sda')
    connection = nbdClient.connect()

    if(args.qemu):
        logger.info("Using qemu tools to query extents")
        extentHandler = extenthandler.ExtentHandler(qemuhelper.qemuHelper('sda'))
    else:
        logger.info("Using nbd to query extents")
        extentHandler = extenthandler.ExtentHandler(connection)

    extents = extentHandler.queryBlockStatus()
    if len(extents) < 1:
        logging.error("No extents found")
        sys.exit(1)

    thinBackupSize = sum([extent.length for extent in extents if extent.data == True])
    fullBackupSize = sum([extent.length for extent in extents])
    logger.info("Found %s extents to backup" % len(extents))
    logger.info("%s bytes imagesize" % fullBackupSize)
    logger.info("%s bytes of used data in image" % thinBackupSize)

    writer = open(args.file,'wb')
    if args.type == "raw":
        logging.info("Creating full provisioned raw backup image")
        writer.truncate(fullBackupSize)
        writer.seek(0)
    else:
        logging.info("Creating thin provisioned stream backup image")
        metadata = sparsestream.SparseStream().dump_metadata(
            fullBackupSize,
            thinBackupSize,
            "none",
            "sda",
            False
        )
        sparsestream.SparseStream().write_frame(writer,
            sparsestream.SparseStreamTypes().META,
            0,
            len(metadata)
        )
        writer.write(metadata)
        writer.write(sparsestream.SparseStreamTypes().TERM)

    for save in extents:
        if save.data == True:
            if args.type == "stream":
                sparsestream.SparseStream().write_frame(writer,
                    sparsestream.SparseStreamTypes().DATA,
                    save.offset,
                    save.length
                )
            if save.length >= nbdClient.maxRequestSize:
                bs = nbdClient.minRequestSize
                assert save.length % bs == 0
                offset = save.offset
                count = int(save.length/bs)
                ct = 1
                while ct <= count:
                    if args.type == "raw":
                        writer.seek(offset)
                    writer.write(connection.pread(bs, offset))
                    ct+=1
                    offset+=bs
            else:
                writer.seek(save.offset)
                writer.write(connection.pread(save.length, save.offset))
            if args.type == "stream":
                writer.write(sparsestream.SparseStreamTypes().TERM)
        else:
            if args.type == "raw":
                writer.seek(save.offset)
            elif args.type == "stream":
                sparsestream.SparseStream().write_frame(writer,
                    sparsestream.SparseStreamTypes().ZERO,
                    save.offset,
                    save.length
                )
    if args.type == "stream":
        sparsestream.SparseStream().write_frame(writer, sparsestream.SparseStreamTypes().STOP, 0, 0)
        writer.close()


if __name__ == "__main__":
    main()
