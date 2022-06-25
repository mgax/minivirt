# MiniVirt – lightweight virtual machine manager

## Installation

You'll need [qemu][], [python3][] and [socat][] installed.

[qemu]: https://www.qemu.org/
[python3]: https://www.python.org/
[socat]: http://www.dest-unreach.org/socat/

* MacOS: `brew install qemu socat`
* Debian: `apt install qemu-system-x86 qemu-utils socat`
* Alpine: `apk add py3-pip qemu qemu-system-x86_64 qemu-img socat tar git`

Then, install _MiniVirt_ and run a checkup:

```shell
pip3 install git+https://github.com/mgax/minivirt
miv doctor
```

## Usage

```shell
miv remote add default https://f003.backblazeb2.com/file/minivirt
miv pull default 'alpine-3.15.4-{arch}' alpine
miv create alpine foo
miv start foo --display
# ... interact with the VM's display ...
miv destroy foo
```

### Images

Display images in the database:

```shell
miv images
```

Commit a VM as an image:

```shell
miv commit foo bar
```

Save the image as a TAR archive:

```shell
miv save bar | gzip -1 > ~/bar.tgz
```

Later, load the image:

```shell
zcat ~/bar.tgz | miv load bar
```

### VMs

Show VMs in the database:

```shell
miv ps -a
```

### SSH

Add these lines to your ssh config (`~/.ssh/config`):

```ssh-config
Host *.miv
  Include ~/.cache/minivirt/*/ssh-config
```

Start the VM, then log into it using SSH:

```shell
miv start foo --daemon --wait-for-ssh=30
ssh foo.miv
# ... do your thing ...
ssh foo.miv poweroff
```

## Development

* Create a virtualenv so you don't interfere with gobally-installed packages:
    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    ```
* Install the repo in edit mode and development dependencies:
    ```shell
    pip3 install -e .
    pip3 install pytest
    ```
* Run the test suite:
    ```shell
    pytest
    # If you're not in a hurry, run the slow tests too:
    pytest --runslow
    ```
