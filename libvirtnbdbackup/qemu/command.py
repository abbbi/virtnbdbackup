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

import logging
import tempfile
import subprocess
from typing import List, Tuple, Union

from libvirtnbdbackup.qemu.exceptions import (
    ProcessError,
)
from libvirtnbdbackup.output import openfile
from libvirtnbdbackup.objects import processInfo

log = logging.getLogger(__name__)


def _readlog(logFile: str, cmd: str) -> str:
    try:
        with openfile(logFile, "rb") as fh:
            return fh.read().decode().strip()
    except Exception as errmsg:
        log.exception(errmsg)
        raise ProcessError(
            f"Failed to execute [{cmd}]: Unable to get error message: {errmsg}"
        ) from errmsg


def _readpipe(p) -> Tuple[str, str]:
    out = p.stdout.read().decode().strip()
    err = p.stderr.read().decode().strip()
    return out, err


def run(cmdLine: List[str], pidFile: str = "", toPipe: bool = False) -> processInfo:
    """Execute passed command"""
    logFileName: str = ""
    logFile: Union[int, tempfile._TemporaryFileWrapper]
    if toPipe is True:
        logFile = subprocess.PIPE
    else:
        # pylint: disable=consider-using-with
        logFile = tempfile.NamedTemporaryFile(
            delete=False, prefix=cmdLine[0], suffix=".log"
        )
        logFileName = logFile.name

    log.debug("CMD: %s", " ".join(cmdLine))
    try:
        with subprocess.Popen(
            cmdLine,
            close_fds=True,
            stderr=logFile,
            stdout=logFile,
        ) as p:
            p.wait()
            log.debug("Return code: %s", p.returncode)
            err: str = ""
            out: str = ""
            if p.returncode != 0:
                log.error("CMD: %s", " ".join(cmdLine))
                log.debug("Read error messages from logfile")
                if toPipe is True:
                    out, err = _readpipe(p)
                else:
                    err = _readlog(logFileName, cmdLine[0])
                raise ProcessError(f"Unable to start [{cmdLine[0]}] error: [{err}]")

            if toPipe is True:
                out, err = _readpipe(p)

            if pidFile != "":
                realPid = int(_readlog(pidFile, ""))
            else:
                realPid = p.pid

            process = processInfo(realPid, logFileName, err, out, pidFile)
            log.debug("Started [%s] process: [%s]", cmdLine[0], process)
    except FileNotFoundError as e:
        raise ProcessError(e) from e

    return process
