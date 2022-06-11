# MiniVirt – lightweight virtual machine manager

## Installation

```shell
python3 -m venv .venv
.venv/bin/pip3 install -r requirements/base.txt
./miv doctor
```

## Usage

```shell
./miv alpine download 3.15.4
./miv create alpine-3.15.4-iso foo --disk=10G
./miv -v alpine bootstrap foo
./miv start foo --display
# ... interact with the VM's display ...
./miv destroy foo
```

### Images

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

### SSH

Add these lines to your ssh config (`~/.ssh/config`):

```ssh-config
Host *.miv
  Include ~/.cache/minivirt/*/ssh-config
```

Start the VM, then log into it using SSH:

```shell
./miv start foo --daemon --wait-for-ssh
ssh foo.miv
# ... do your thing ...
ssh foo.miv poweroff
```
