"""
Copyright (C) 2026  Michael Ablassmeier <abi@grinser.de>

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

FTP input/output target example plugin for virtnbdbackup.
"""

import fnmatch
import ftplib
import io
import logging
import os
import posixpath
import zlib
from datetime import datetime
from typing import Any, List, Optional, Tuple
from urllib.parse import unquote, urlsplit, urlunsplit

from libvirtnbdbackup.output import exceptions
from libvirtnbdbackup.output.target.base import OutputTarget

log = logging.getLogger("ftp-output-target")

USERNAME_ENV = "VIRTNBDBACKUP_FTP_USERNAME"
PASSWORD_ENV = "VIRTNBDBACKUP_FTP_PASSWORD"


class _FTPFile:
    """File-like wrapper around an FTP data connection."""

    def __init__(self, target: "FTPOutputTarget", remote_path: str, mode: str) -> None:
        self._target = target
        self._remote_path = remote_path
        self._mode = mode
        self._binary = "b" in mode
        self._readable = "r" in mode or "+" in mode
        self._writable = any(flag in mode for flag in ("w", "a", "+"))
        self._checksum = 1
        self._connection, self._file = target._transfer(remote_path, mode)

    @property
    def closed(self) -> bool:
        return self._file.closed

    def readable(self) -> bool:
        return self._readable

    def writable(self) -> bool:
        return self._writable

    def seekable(self) -> bool:
        return False

    def read(self, size: int = -1) -> Any:
        if not self._readable:
            raise io.UnsupportedOperation("not readable")
        data = self._file.read(size)
        return data if self._binary else data.decode()

    def write(self, data: Any) -> int:
        if not self._writable:
            raise io.UnsupportedOperation("not writable")
        encoded = data.encode() if isinstance(data, str) else data
        self._checksum = zlib.adler32(encoded, self._checksum)
        return self._file.write(encoded)

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        raise io.UnsupportedOperation("FTP streams are not seekable")

    def tell(self) -> int:
        raise io.UnsupportedOperation("FTP streams do not expose a file position")

    def truncate(self, size: Optional[int] = None) -> int:
        raise io.UnsupportedOperation("FTP streams cannot be truncated")

    def flush(self) -> None:
        self._file.flush()

    def __enter__(self) -> "_FTPFile":
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._file.close()
            self._connection.close()
            self._target._complete_transfer()
            if self._writable:
                self._target._last_checksum = self._checksum
        finally:
            if not self._file.closed:
                self._file.close()
            self._connection.close()


class _FTPLogHandler(logging.StreamHandler):
    """Logging handler owning a dedicated FTP connection and stream."""

    def __init__(self, target_file: str) -> None:
        self._target = FTPOutputTarget()
        super().__init__(self._target.open(target_file, "w"))

    def close(self) -> None:
        try:
            if self.stream is not None:
                self.stream.close()
                self.stream = None
            self._target.finish()
        finally:
            super().close()


class FTPOutputTarget(OutputTarget):
    """Store and retrieve backup files on an FTP server."""

    supports_input = True
    supported_backup_modes = ["full", "inc", "copy"]

    def __init__(self) -> None:
        self._ftp: Optional[ftplib.FTP] = None
        self._host: Optional[str] = None
        self._port = 21
        self._current: Optional[_FTPFile] = None
        self._last_checksum = 1

        self._username = os.environ.get(USERNAME_ENV)
        self._password = os.environ.get(PASSWORD_ENV)
        if self._username is None or self._password is None:
            missing = [
                name
                for name, value in (
                    (USERNAME_ENV, self._username),
                    (PASSWORD_ENV, self._password),
                )
                if value is None
            ]
            raise exceptions.OutputPluginException(
                "Missing FTP credential environment variable(s): " + ", ".join(missing)
            )

    def _location(self, value: str) -> Tuple[str, str]:
        parsed = urlsplit(value)
        if parsed.scheme:
            if parsed.scheme.lower() != "ftp":
                raise exceptions.OutputException(
                    f"FTP target requires an ftp:// URL, got [{value}]"
                )
            if parsed.username is not None or parsed.password is not None:
                raise exceptions.OutputException(
                    "Do not put FTP credentials in the URL; use "
                    f"{USERNAME_ENV} and {PASSWORD_ENV}"
                )
            if not parsed.hostname:
                raise exceptions.OutputException(f"FTP URL has no host: [{value}]")
            host = parsed.hostname
            port = parsed.port or 21
            if self._host is not None and (host, port) != (self._host, self._port):
                raise exceptions.OutputException(
                    "One FTP target instance cannot access multiple servers"
                )
            self._host, self._port = host, port
            return self._url(unquote(parsed.path) or "/"), unquote(parsed.path) or "/"

        if self._host is None:
            raise exceptions.OutputException(
                f"FTP path must be an ftp:// URL before a server is configured: [{value}]"
            )
        path = value if value.startswith("/") else f"/{value}"
        return self._url(path), path

    def _url(self, path: str) -> str:
        assert self._host is not None
        host = f"[{self._host}]" if ":" in self._host else self._host
        netloc = host if self._port == 21 else f"{host}:{self._port}"
        return urlunsplit(("ftp", netloc, path, "", ""))

    def _client(self) -> ftplib.FTP:
        if self._ftp is None:
            if self._host is None:
                raise exceptions.OutputException("FTP server is not configured")
            try:
                client = ftplib.FTP()
                client.connect(self._host, self._port)
                client.login(self._username, self._password)
                self._ftp = client
            except ftplib.all_errors as error:
                raise exceptions.OutputOpenException(
                    f"Connecting to FTP server [{self._host}:{self._port}] failed: {error}"
                ) from error
        return self._ftp

    def _mkdirs(self, path: str) -> None:
        client = self._client()
        current = "/"
        for component in filter(None, path.split("/")):
            current = posixpath.join(current, component)
            try:
                client.mkd(current)
            except ftplib.error_perm as error:
                # FTP has no portable "mkdir -p" response. Verify that an
                # existing path really is a directory before ignoring 550.
                previous = client.pwd()
                try:
                    client.cwd(current)
                    client.cwd(previous)
                except ftplib.all_errors:
                    raise exceptions.OutputCreateDirectory(
                        f"Creating FTP directory [{current}] failed: {error}"
                    ) from error

    def _transfer(self, path: str, mode: str) -> Tuple[Any, Any]:
        if any(flag in mode for flag in ("w", "a", "+")):
            self._mkdirs(posixpath.dirname(path))
        command = "RETR" if mode.startswith("r") else "APPE" if "a" in mode else "STOR"
        file_mode = "rb" if mode.startswith("r") else "wb"
        try:
            connection = self._client().transfercmd(f"{command} {path}")
            return connection, connection.makefile(file_mode)
        except ftplib.all_errors as error:
            raise exceptions.OutputOpenException(
                f"Opening FTP transfer for [{path}] failed: {error}"
            ) from error

    def _complete_transfer(self) -> None:
        try:
            self._client().voidresp()
        except ftplib.all_errors as error:
            raise exceptions.OutputException(
                f"Completing FTP transfer failed: {error}"
            ) from error

    def _upload(self, path: str, source: Any) -> None:
        self._mkdirs(posixpath.dirname(path))
        try:
            self._client().storbinary(f"STOR {path}", source)
        except ftplib.all_errors as error:
            raise exceptions.OutputException(
                f"Uploading FTP file [{path}] failed: {error}"
            ) from error

    def create(self, targetDir: str) -> None:
        """Create a directory, including missing parents, on the FTP server."""
        _, path = self._location(targetDir)
        self._mkdirs(path)

    def open(self, targetFile: str, mode: str = "wb") -> _FTPFile:
        """Open a streaming FTP-backed file."""
        if mode not in ("r", "rb", "w", "wb", "a", "ab"):
            raise exceptions.OutputOpenException(f"Unsupported FTP mode [{mode}]")
        _, path = self._location(targetFile)
        try:
            self._current = _FTPFile(self, path, mode)
            return self._current
        except exceptions.OutputException:
            raise
        except (OSError, ValueError) as error:
            raise exceptions.OutputOpenException(
                f"Opening FTP file [{targetFile}] failed: {error}"
            ) from error

    def write(self, data: bytes) -> int:
        if self._current is None:
            raise exceptions.OutputException("No FTP file is open")
        return self._current.write(data)

    def read(self, size: int = -1) -> Any:
        if self._current is None:
            raise exceptions.OutputException("No FTP file is open")
        return self._current.read(size)

    def seek(self, target: int, whence: int = io.SEEK_SET) -> int:
        raise exceptions.OutputException("FTP streams are not seekable")

    def truncate(self, size: int) -> None:
        raise exceptions.OutputException("FTP streams cannot be truncated")

    def flush(self) -> None:
        if self._current is not None:
            self._current.flush()

    def close(self) -> None:
        if self._current is not None:
            self._current.close()
            self._current = None

    def checksum(self) -> int:
        checksum = self._last_checksum
        self._last_checksum = 1
        return checksum

    def add_file(self, source: str, target: Optional[str] = None) -> None:
        if target is None:
            target = os.path.basename(source)
        _, remote_path = self._location(target)
        try:
            with open(source, "rb") as source_file:
                self._upload(remote_path, source_file)
        except OSError as error:
            raise exceptions.OutputException(
                f"Reading local file [{source}] failed: {error}"
            ) from error

    def add_tree(self, source: str) -> None:
        for directory, _, files in os.walk(source):
            for filename in files:
                local_path = os.path.join(directory, filename)
                self.add_file(local_path, local_path)

    def exists(self, path: str) -> bool:
        _, remote_path = self._location(path)
        try:
            self._client().size(remote_path)
            return True
        except ftplib.error_perm:
            try:
                previous = self._client().pwd()
                self._client().cwd(remote_path)
                self._client().cwd(previous)
                return True
            except ftplib.all_errors:
                return False

    def _modified(self, path: str) -> datetime:
        try:
            response = self._client().sendcmd(f"MDTM {path}")
            return datetime.strptime(response.split()[-1], "%Y%m%d%H%M%S")
        except ftplib.all_errors + (ValueError,):
            return datetime.min

    def list(self, path: str, pattern: str, key: Optional[int] = None) -> List[str]:
        _, remote_path = self._location(path)
        try:
            names = self._client().nlst(remote_path)
        except ftplib.error_perm as error:
            if str(error).startswith("550"):
                return []
            raise exceptions.OutputException(
                f"Listing FTP directory [{remote_path}] failed: {error}"
            ) from error

        normalized_names = [
            name if name.startswith("/") else posixpath.join(remote_path, name)
            for name in names
        ]
        matches = [
            name
            for name in normalized_names
            if fnmatch.fnmatch(posixpath.basename(name.rstrip("/")), pattern)
        ]
        matches.sort(key=self._modified)
        urls = [
            self._url(name if name.startswith("/") else f"/{name}") for name in matches
        ]
        if key is not None:
            try:
                return [urls[key]]
            except IndexError:
                return []
        return urls

    def rename(self, source: str, target: str) -> None:
        """Rename a file on the FTP server."""
        _, source_path = self._location(source)
        _, target_path = self._location(target)
        try:
            self._client().rename(source_path, target_path)
        except ftplib.all_errors as error:
            raise exceptions.OutputException(
                f"Renaming FTP file [{source_path}] to [{target_path}] failed: {error}"
            ) from error

    def remove(self, path: str) -> None:
        """Remove a file from the FTP server."""
        _, remote_path = self._location(path)
        try:
            self._client().delete(remote_path)
        except ftplib.all_errors as error:
            raise exceptions.OutputException(
                f"Removing FTP file [{remote_path}] failed: {error}"
            ) from error

    def finish(self) -> None:
        if self._ftp is not None:
            try:
                self._ftp.quit()
            except ftplib.all_errors:
                self._ftp.close()
            finally:
                self._ftp = None

    def logging_handler(self, target_file: str) -> logging.Handler:
        """Return a handler streaming logs over a dedicated FTP connection."""
        return _FTPLogHandler(target_file)
