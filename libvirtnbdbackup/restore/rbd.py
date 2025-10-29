# libvirtnbdbackup/restore/_rbd.py
import os
import shlex
import socket
import subprocess
import tempfile
import time

class NbdkitServer:
    def __init__(self, blockmap_path, data_path):
        self.blockmap_path = blockmap_path
        self.data_path = data_path
        self.sock = None
        self.proc = None

    def __enter__(self):
        self.sock = tempfile.mktemp(prefix="virtnbdrestore.", suffix=".sock", dir="/var/tmp")
        # virtnbd-nbdkit-plugin is shipped by the project; use it to serve our backup as NBD
        cmd = [
            "nbdkit",
            "--exit-with-parent",
            "--unix", self.sock,
            "--threads", "1",
            "python",
            "script=virtnbd-nbdkit-plugin",
            f"blockmap={self.blockmap_path}",
            f"image={self.data_path}",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # wait until the socket is ready
        for _ in range(50):
            if os.path.exists(self.sock):
                try:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                        s.connect(self.sock)
                        break
                except OSError:
                    pass
            time.sleep(0.1)
        return self.sock

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.proc:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            if self.sock and os.path.exists(self.sock):
                os.unlink(self.sock)
        except Exception:
            pass


def qemu_img_convert_from_unix_nbd_to_rbd(unix_sock, rbd_url, preallocate=False):
    """
    Convert NBD served at `unix_sock` to RBD image (rbd:pool/image).
    """
    src = f"nbd+unix:///?socket={unix_sock}"
    cmd = ["qemu-img", "convert", "-f", "raw", "-O", "raw", src, rbd_url]
    if preallocate:
        cmd[4:4] = ["-o", "preallocation=falloc"]
    subprocess.run(cmd, check=True)

