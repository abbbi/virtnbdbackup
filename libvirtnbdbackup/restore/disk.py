#!/usr/bin/python3
"""
Enable in-place RBD overwrite via virtnbdrestore:
- Detect if the RBD image already exists and pass `-n` to qemu-img convert.
- Handle both copy-mode (flat raw) and sparse-stream restores.
"""
import logging
import os
import re
import subprocess
from typing import Optional
from argparse import Namespace

from libvirtnbdbackup import virt
from libvirtnbdbackup import common as lib
from libvirtnbdbackup.objects import DomainDisk
from libvirtnbdbackup.restore import server
from libvirtnbdbackup.restore import files
from libvirtnbdbackup.restore import image as image_mod
from libvirtnbdbackup.restore import header
from libvirtnbdbackup.restore import data
from libvirtnbdbackup.restore import vmconfig
from libvirtnbdbackup.sparsestream import types
from libvirtnbdbackup.sparsestream import streamer
from libvirtnbdbackup.exceptions import RestoreError, UntilCheckpointReached
from libvirtnbdbackup.nbdcli.exceptions import NbdConnectionTimeout


log = logging.getLogger(__name__)
_RBD_RE = re.compile(r"^rbd:(?P<pool>[^/]+)(?:/(?P<image>[^/]+))?$")


def _parse_rbd_target(target_str: Optional[str], disk: DomainDisk) -> Optional[str]:
    """
    Accepts:
      - 'rbd:<pool>/<image>'  (explicit image)
      - 'rbd:<pool>'          (derive image from disk filename)
    Returns full 'rbd:<pool>/<image>' or None if not rbd.
    """
    if not target_str or not isinstance(target_str, str):
        return None
    m = _RBD_RE.match(target_str)
    if not m:
        return None
    pool = m.group("pool")
    image_name = m.group("image")
    if not image_name:
        image_name = getattr(disk, "filename", disk.target)
    return f"rbd:{pool}/{image_name}"


def _rbd_pool_image(rbd_url: str) -> Optional[tuple]:
    """Extract (pool, image) from rbd:<pool>/<image>."""
    m = _RBD_RE.match(rbd_url)
    if not m or not m.group("image"):
        return None
    return (m.group("pool"), m.group("image"))


def _rbd_target_for_disk(base_str: Optional[str], disk: DomainDisk, is_multi: bool) -> Optional[str]:
    """
    Build a per-disk RBD URL from 'rbd:<pool>[/<image>]'.

    Rules:
      - 'rbd:<pool>'                -> image := <disk-filename-base> (or target dev if no filename)
      - 'rbd:<pool>/<image>':
            if is_multi == True     -> image := '<image>-<dev>'   (e.g., '-vda', '-vdb')
            else                    -> image := '<image>' (as-is)
    """
    if not base_str or not isinstance(base_str, str):
        return None
    m = _RBD_RE.match(base_str)
    if not m:
        return None

    pool  = m.group("pool")
    image = m.group("image")
    dev   = getattr(disk, "target", "disk")

    # Derive a safe base from filename if pool-only used
    if not image:
        fname = getattr(disk, "filename", None) or dev
        base  = os.path.splitext(os.path.basename(fname))[0] or dev
        image = base
    else:
        if is_multi:
            image = f"{image}-{dev}"

    return f"rbd:{pool}/{image}"


def _rbd_exists(rbd_url: str) -> bool:
    """
    Return True if the RBD image exists (ceph CLI required).
    """
    pi = _rbd_pool_image(rbd_url)
    if not pi:
        return False
    pool, image = pi
    try:
        # rbd info <pool>/<image> -> 0 if exists
        subprocess.run(
            ["rbd", "info", f"{pool}/{image}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _qemu_img_convert_raw_to_rbd(src: str, rbd_url: str) -> None:
    """
    Convert raw file to RBD. If the image already exists, pass -n to overwrite in place.
    """
    exists = _rbd_exists(rbd_url)
    cmd = ["qemu-img", "convert", "-f", "raw", "-O", "raw"]
    if exists:
        cmd.append("-n")  # do not try to create; overwrite existing image
        log.info("Target RBD exists; using in-place overwrite (-n).")
    cmd.extend([src, rbd_url])
    log.debug("Executing: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _backingstore(args: Namespace, disk: DomainDisk) -> None:
    """Warn if the VM was on a snapshot image and user didn't request config adjust."""
    if len(disk.backingstores) > 0 and not args.adjust_config:
        logging.warning(
            "Target image [%s] seems to be a snapshot image.", disk.filename
        )
        logging.warning("Target virtual machine configuration must be altered!")
        logging.warning("Configured backing store images must be changed.")


def restore(  # pylint: disable=too-many-branches,too-many-statements,too-many-locals
    args: Namespace, ConfigFile: str, virtClient: virt.client
) -> bytes:
    """Handle disk restore operation and adjust virtual machine configuration accordingly."""
    from libvirtnbdbackup.virt import xml  # local import to avoid altering module imports

    stream = streamer.SparseStream(types)

    # Load and normalize config for disk parsing
    vmConfig = vmconfig.read(ConfigFile)
    vmConfig = vmconfig.changeVolumePathes(args, vmConfig).decode()

    # Parse VM name and original disk sources (to detect in-place overwrite)
    tree = xml.asTree(vmConfig)
    try:
        original_vm_name = tree.find("name").text
    except Exception:
        original_vm_name = None

    original_rbd_by_dev = {}
    for d in tree.xpath("devices/disk"):
        try:
            dev = d.xpath("target")[0].get("dev")
        except Exception:
            continue
        if d.get("type") == "network":
            src = d.find("source")
            if src is not None and src.get("protocol") == "rbd":
                name = src.get("name")  # expected "pool/image"
                if name:
                    original_rbd_by_dev[dev] = name

    vmDisks = virtClient.getDomainDisks(args, vmConfig)
    if not vmDisks:
        raise RestoreError("Unable to parse disks from config")

    # Determine if restoring multiple disks in this invocation
    restoreDisks = [d for d in vmDisks if args.disk in (None, d.target)]
    is_multi = len(restoreDisks) > 1

    # We will stop the original domain once (lazy), if we detect we're about to overwrite its disks
    domain_stopped = False

    restConfig: bytes = vmConfig.encode()
    for disk in vmDisks:
        if args.disk not in (None, disk.target):
            logging.info("Skipping disk [%s] for restore", disk.target)
            continue

        restoreDisk = lib.getLatest(args.input, f"{disk.target}*.data")
        logging.debug("Restoring disk: [%s]", restoreDisk)
        if len(restoreDisk) < 1:
            logging.warning(
                "No backup file for disk [%s] found, assuming it has been excluded.",
                disk.target,
            )
            if args.adjust_config is True:
                restConfig = vmconfig.removeDisk(restConfig.decode(), disk.target)
            continue

        # Decide targets (filesystem vs RBD). For RBD, ensure per-disk unique naming when needed.
        targetFile = files.target(args, disk)

        rbdTarget = _rbd_target_for_disk(getattr(args, "output", None), disk, is_multi)
        isRbdTarget = rbdTarget is not None
        if isRbdTarget:
            logging.info("Disk [%s]: restore target is Ceph RBD [%s]", disk.target, rbdTarget)

        # If this is an in-place overwrite (target RBD equals original RBD for this disk),
        # stop the original domain once before writing.
        if isRbdTarget and not domain_stopped and original_vm_name:
            # rbdTarget is "rbd:pool/image" -> compare the "pool/image" part
            try:
                pool, image = _rbd_pool_image(rbdTarget)  # returns (pool, image)
            except Exception:
                pool, image = (None, None)
            if pool and image:
                original_name_for_dev = original_rbd_by_dev.get(disk.target)
                if original_name_for_dev == f"{pool}/{image}":
                    logging.info(
                        "In-place overwrite detected for disk [%s] (%s); "
                        "ensuring domain [%s] is stopped before restore.",
                        disk.target, original_name_for_dev, original_vm_name,
                    )
                    if not virtClient.ensureDomainStopped(original_vm_name, graceful_timeout=60):
                        raise RestoreError(
                            f"Unable to stop domain [{original_vm_name}] before in-place restore."
                        )
                    domain_stopped = True

        # Detect copy-mode backups (flat raw). In this case, do NOT read sparse headers.
        is_copy_backup = any(".copy." in p for p in restoreDisk)

        # ---- COPY BACKUP HANDLING ----
        if is_copy_backup:
            src_raw = restoreDisk[0]  # flat raw image
            if isRbdTarget:
                logging.info("Converting flat raw [%s] -> [%s] via qemu-img convert (raw).", src_raw, rbdTarget)
                try:
                    _qemu_img_convert_raw_to_rbd(src_raw, rbdTarget)
                except subprocess.CalledProcessError as e:
                    raise RestoreError(f"qemu-img convert to RBD failed: {e}") from e

                if args.adjust_config is True:
                    restConfig = vmconfig.adjust(args, disk, restConfig.decode(), rbdTarget)

                continue

            # Filesystem target: just copy the flat raw
            logging.info("Restoring flat raw copy [%s] to [%s]", src_raw, targetFile)
            lib.copy(args, src_raw, targetFile)

            if args.adjust_config is True:
                restConfig = vmconfig.adjust(args, disk, restConfig.decode(), targetFile)

            continue

        # ---- SPARSE-STREAM (FULL/DIFF) HANDLING ----
        if "full" not in restoreDisk[0] and "copy" not in restoreDisk[0]:
            logging.error(
                "[%s]: Unable to locate base full or copy backup.", restoreDisk[0]
            )
            raise RestoreError("Failed to locate backup.")

        cptnum = -1
        if args.until is not None:
            cptnum = int(args.until.split(".")[-1])

        meta = header.get(restoreDisk[cptnum], stream)

        # For RBD target, reconstruct into a local temp raw first, then push to RBD.
        if isRbdTarget:
            tmp_dir = getattr(args, "tmpdir", "/var/tmp")
            try:
                os.makedirs(tmp_dir, exist_ok=True)
            except Exception as e:  # noqa: BLE001
                raise RestoreError(f"Failed to prepare temp dir [{tmp_dir}]: {e}") from e
            localTarget = os.path.join(
                tmp_dir, f"virtnbdrestore.{disk.target}.{os.getpid()}.img"
            )
            createTarget = localTarget
            logging.info("Creating local target for RBD stream: [%s]", createTarget)
        else:
            createTarget = targetFile

        try:
            image_mod.create(args, meta, createTarget, args.sshClient)
        except RestoreError as errmsg:
            raise RestoreError("Creating target image failed.") from errmsg

        try:
            connection = server.start(args, meta["diskName"], createTarget, virtClient)
        except NbdConnectionTimeout as e:
            raise RestoreError(e) from e

        for dataFile in restoreDisk:
            try:
                data.restore(args, stream, dataFile, createTarget, connection)
            except UntilCheckpointReached:
                break
            except RestoreError:
                break

        _backingstore(args, disk)

        if isRbdTarget:
            logging.info("Streaming reconstructed image into Ceph RBD: [%s] -> [%s]", createTarget, rbdTarget)
            try:
                _qemu_img_convert_raw_to_rbd(createTarget, rbdTarget)
            except subprocess.CalledProcessError as e:
                raise RestoreError(f"qemu-img convert to RBD failed: {e}") from e
            finally:
                try:
                    os.remove(createTarget)
                except Exception:  # noqa: BLE001
                    pass

        if args.adjust_config is True:
            adjustTarget = rbdTarget if isRbdTarget else targetFile
            restConfig = vmconfig.adjust(args, disk, restConfig.decode(), adjustTarget)

        logging.debug("Closing NBD connection")
        connection.disconnect()

    if args.adjust_config is True:
        restConfig = vmconfig.removeUuid(restConfig.decode())
        restConfig = vmconfig.setVMName(args, restConfig.decode())

    return restConfig

