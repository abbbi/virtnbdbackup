"""
Copyright (C) 2023  Michael Ablassmeier <abi@grinser.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import sys
import glob
import json
import logging
import logging.handlers
import signal
import shutil
import pprint
from time import time
from threading import current_thread
from argparse import Namespace
from typing import Optional, List, Any, Union, Dict
from tqdm import tqdm
import colorlog

from libvirtnbdbackup import ssh
from libvirtnbdbackup.ssh.exceptions import sshError
from libvirtnbdbackup import output
from libvirtnbdbackup.logcount import logCount

log = logging.getLogger("lib")

logFormat = (
    "%(asctime)s %(levelname)s %(name)s %(module)s - %(funcName)s"
    " [%(threadName)s]: %(message)s"
)
logFormatColored = (
    "%(green)s%(asctime)s%(reset)s%(blue)s %(log_color)s%(levelname)s%(reset)s "
    "%(name)s %(module)s - %(funcName)s"
    " [%(threadName)s]: %(log_color)s %(message)s"
)

logDateFormat = "[%Y-%m-%d %H:%M:%S]"
defaultCheckpointName = "virtnbdbackup"


def argparse(parser) -> Namespace:
    """Parse arguments"""
    return parser.parse_args()


def printVersion(version) -> None:
    """Print version and passed arguments"""
    log.info("Version: %s Arguments: %s", version, " ".join(sys.argv))


def humanize(num, suffix="B"):
    """Print size in human readable output"""
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def setThreadName(tn="main") -> None:
    """Set thread name reported by logging function"""
    current_thread().name = tn


def setLogLevel(verbose: bool) -> int:
    """Set loglevel"""
    level = logging.INFO
    if verbose is True:
        level = logging.DEBUG

    return level


def sshSession(
    args: Namespace, remoteHost: str, mode: ssh.Mode = ssh.Mode.DOWNLOAD
) -> Union[ssh.client, None]:
    """Use ssh to copy remote files"""
    try:
        return ssh.client(remoteHost, args.ssh_user, args.ssh_port, mode)
    except sshError as err:
        log.warning("Failed to setup SSH connection: [%s]", err)

    return None


def getLogFile(fileName: str) -> Optional[logging.FileHandler]:
    """Try setup log handler, if this fails, something is already
    wrong, but we can at least provide correct error message."""
    try:
        return logging.FileHandler(fileName)
    except OSError as e:
        logging.error("Failed to open logfile: [%s].", e)
        return None


def safeInfo(msg, *args, **kwargs):
    """Use tqdm redirect to not destroy progress bars"""
    rootlog = logging.getLogger("")
    kwargs.setdefault("stacklevel", 2)
    try:
        from tqdm.contrib.logging import (  # pylint: disable=import-outside-toplevel
            logging_redirect_tqdm,
        )
    except ModuleNotFoundError:
        rootlog.info(msg, *args, **kwargs)
        return

    with logging_redirect_tqdm():
        rootlog.info(msg, *args, **kwargs)


def configLogger(
    args: Namespace, fileLog: Optional[logging.FileHandler], counter: logCount
):
    """Setup logging"""
    syslog = False
    try:
        syslog = args.syslog is True
    except AttributeError:
        pass
    handler: List[Any]
    handler = [
        fileLog,
        counter,
    ]
    stderrh = logging.StreamHandler(stream=sys.stderr)
    if args.nocolor is False:
        formatter = colorlog.ColoredFormatter(
            logFormatColored,
            datefmt=logDateFormat,
            log_colors={
                "WARNING": "yellow",
                "ERROR": "red",
                "DEBUG": "cyan",
                "CRITICAL": "red",
            },
        )
        stderrh.setFormatter(formatter)
    if args.quiet is False:
        handler.append(stderrh)
    if syslog is True:
        handler.append(logging.handlers.SysLogHandler(address="/dev/log"))
    logging.basicConfig(
        level=setLogLevel(args.verbose),
        format=logFormat,
        datefmt=logDateFormat,
        handlers=handler,
    )


def hasFullBackup(args: Namespace) -> int:
    """Check if full backup file exists in target directory"""
    fullFiles = glob.glob(f"{args.output}/*.full.data")
    return len(fullFiles) > 0


def exists(args: Namespace, filePath: str) -> bool:
    """Check if file exists either remotely or locally."""
    if args.sshClient:
        return args.sshClient.exists(filePath)

    return os.path.exists(filePath)


def targetIsEmpty(args: Namespace) -> bool:
    """Check if target directory does not include an backup
    already (no .data or .data.partial files)"""
    if exists(args, args.output) and args.level in ("full", "copy", "auto"):
        dirList = glob.glob(f"{args.output}/*.data*")
        if len(dirList) > 0:
            return False

    return True


def getLatest(targetDir: str, search: str, key=None) -> List[str]:
    """get the last backed up file matching search
    from the backupset, used to find latest vm config,
    data files or data files by disk.
    """
    ret: List[str] = []
    try:
        files = glob.glob(f"{targetDir}/{search}")
        files.sort(key=os.path.getmtime)

        if key is not None:
            ret.append(files[key])
        else:
            ret = files

        log.debug("Sorted data files: \n%s", pprint.pformat(ret))
        return ret
    except IndexError:
        return []


def hasQcowDisks(diskList: List[Any]) -> bool:
    """Check if the list of attached disks includes at least one
    qcow image based disk, else checkpoint handling can be
    skipped and backup module falls back to type copy"""
    for disk in diskList:
        if disk.format.startswith("qcow"):
            return True

    return False


def copy(args: Namespace, source: str, target: str) -> None:
    """Copy file, handle exceptions"""
    try:
        if args.sshClient:
            args.sshClient.copy(source, target)
        else:
            shutil.copyfile(source, target)
    except OSError as e:
        log.warning("Failed to copy [%s] to [%s]: [%s]", source, target, e)
    except sshError as e:
        log.warning("Remote copy from [%s] to [%s] failed: [%s]", source, target, e)


def remove(args: Namespace, file: str) -> None:
    """Remove file either locally or remote"""
    try:
        if args.sshClient:
            args.sshClient.run(f"rm -f {file}")
        else:
            os.remove(file)
        log.debug("Removed: [%s]", file)
    except FileNotFoundError:
        pass
    except OSError as e:
        log.warning("Failed to remove [%s]: [%s]", file, e)
    except sshError as e:
        log.warning("Remote remove failed: [%s]: [%s]", file, e)


def progressBar(total: int, desc: str, args: Namespace, count=0) -> tqdm:
    """Return tqdm object"""
    return tqdm(
        total=total,
        desc=desc,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        disable=args.noprogress,
        position=count,
        leave=False,
    )


def killProc(pid: int) -> bool:
    """Attempt kill PID"""
    log.debug("Killing PID: %s", pid)
    while True:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except ProcessLookupError:
            return True


def getIdent(args: Namespace) -> Union[str, int]:
    """Used to get an unique identifier for target files,
    usually checkpoint name is used, but if no checkpoint
    is created, we use timestamp"""
    try:
        ident = args.cpt.name
    except AttributeError:
        ident = int(time())
    if args.level == "diff":
        ident = int(time())
    if args.level == "copy":
        ident = "copy"

    return ident


def dumpExtentJson(extents) -> str:
    """Dump extent object as json"""
    extList = []
    for extent in extents:
        ext = {}
        ext["start"] = extent.offset
        ext["length"] = extent.length
        ext["data"] = extent.data
        extList.append(ext)

    return json.dumps(extList, indent=4, sort_keys=True)


def dumpMetaData(dataFile: str, stream):
    """read metadata header"""
    with output.openfile(dataFile, "rb") as reader:
        _, _, length = stream.readFrame(reader)
        return stream.loadMetadata(reader.read(length))


def isCompressed(meta: Dict[str, str]) -> bool:
    """Return true if stream is compressed"""
    try:
        version = meta["stream-version"] == 2
    except KeyError:
        version = meta["streamVersion"] == 2

    if version:
        if meta["compressed"] is not False:
            return True

    return False
