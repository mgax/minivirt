# MiniVirt – lightweight virtual machine manager

## Installation

```shell
python3 -m venv .venv
.venv/bin/pip3 install -r requirements/base.txt
./miv doctor
```

## Usage

```shell
./miv alpine download 3.15.4 alpine-iso
./miv -v alpine install alpine-iso foo 10G
./miv start foo --display
# ... interact with the VM's display ...
./miv destroy foo
```

### Images

Display images in the database:

```shell
./miv images
```

Commit a VM as an image:

```shell
./miv commit foo bar
```

Save the image as a TAR archive:

```shell
./miv save bar | gzip -1 > ~/bar.tgz
```

Later, load the image:

```shell
zcat ~/bar.tgz | ./miv load bar
```

### VMs

Show VMs in the database:

```shell
./miv ps -a
```

### SSH

Add these lines to your ssh config (`~/.ssh/config`):

```ssh-config
Host *.miv
  Include ~/.cache/minivirt/*/ssh-config
```

Start the VM, then log into it using SSH:

```shell
./miv start foo --daemon --wait-for-ssh=30
ssh foo.miv
# ... do your thing ...
ssh foo.miv poweroff
```

## Development

To run the test suite:

```shell
.venv/bin/pip3 install -r requirements/dev.txt
.venv/bin/pytest
```
