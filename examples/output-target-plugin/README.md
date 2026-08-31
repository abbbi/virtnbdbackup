# Example output target plugin

This directory contains a minimal, installable output target plugin for
`virtnbdbackup`. The plugin extends the built-in directory target and logs each
file it opens. It is intentionally small so the registration and packaging
pieces remain easy to see.

## Install

Install `virtnbdbackup` first, then install the example into the same Python
environment:

```console
python3 -m pip install ./examples/output-target-plugin
```

For development, use an editable installation:

```console
python3 -m pip install --editable ./examples/output-target-plugin
```

The package registers `ExampleDirectoryTarget` under the name
`example-directory` through the `virtnbdbackup.output_targets` setuptools
entry-point group.

## Use

Select the installed plugin with `--output-target`:

```console
virtnbdbackup \
  --domain example-vm \
  --level copy \
  --output /var/backups/example-vm \
  --output-target example-directory
```

Omitting `--output-target` preserves the normal behavior: directory output is
used for a filesystem path, while `-o -` selects the streaming ZIP target.

## Implement another plugin

Plugin classes must inherit from
`libvirtnbdbackup.output.target.OutputTarget`. A directory-compatible plugin
can instead inherit from the built-in `Directory` implementation, as this
example does.

The required methods are `create`, `open`, `write`, `close`, and `checksum`.
Plugins may also implement `add_file`, `add_tree`, `add_stream`, and `finish`
when their backend needs to collect existing files or finalize a container.

Expose the class from the plugin package with this entry-point group:

```python
entry_points={
    "virtnbdbackup.output_targets": [
        "my-target = my_package:MyOutputTarget",
    ],
}
```

The entry-point name is the value passed to `--output-target`.
