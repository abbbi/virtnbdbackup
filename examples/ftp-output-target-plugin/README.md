# FTP output target plugin

This example plugin stores `virtnbdbackup` output on a standard FTP server and
can read that output through `virtnbdrestore`. It uses only Python's standard
library and registers the output target name `ftp`.

## Install

Install the plugin into the same Python environment as `virtnbdbackup`:

```console
python3 -m pip install ./examples/ftp-output-target-plugin
```

## Credentials

The username and password are read only from these environment variables:

```console
export VIRTNBDBACKUP_FTP_USERNAME='backup-user'
export VIRTNBDBACKUP_FTP_PASSWORD='secret'
```

Do not include credentials in the FTP URL. This avoids exposing them in the
process list, logs, or shell history. Protect the environment of the backup
process appropriately.

## Backup

Use an `ftp://` URL as the output directory:

```console
virtnbdbackup \
  --domain example-vm \
  --level copy \
  --output ftp://server/virtual-machines/example-vm \
  --output-target ftp
```

A non-default port can be included, for example
`ftp://server:21/backups/example-vm`.

## Restore

```console
virtnbdrestore \
  --input ftp://backup.example.net/virtual-machines/example-vm \
  --input-source ftp \
  --output /var/lib/libvirt/images/example-vm
```

## Streaming behavior

The plugin streams files directly over FTP without creating local temporary
copies. The backup logfile is also streamed to FTP while the backup runs. FTP
streams do not support seeking or truncation, so the plugin supports the default
`--type stream` output but not raw disk output.

FTP sends credentials and data without transport encryption. Use this plugin
only on a trusted network; use an encrypted backend for untrusted networks.
