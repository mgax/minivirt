# MiniVirt – lightweight virtual machine manager

## Installation

```shell
python3 -m venv .venv
.venv/bin/pip3 install -r requirements/base.txt
./minivirt.sh doctor
```

## Usage

```shell
./minivirt.sh alpine download 3.15.4
./minivirt.sh create alpine-3.15.4-iso foo --disk=10G
./minivirt.sh -v alpine bootstrap foo
./minivirt.sh start foo --display
# ... interact with the VM's display ...
./minivirt.sh destroy foo
```

### Images

Commit a VM as an image:

```shell
./minivirt.sh commit foo bar
```

Save the image as a TAR archive:

```shell
./minivirt.sh save bar | gzip -1 > ~/bar.tgz
```

Later, load the image:

```shell
zcat ~/bar.tgz | ./minivirt.sh load bar
```

### SSH

Add these lines to your ssh config (`~/.ssh/config`):

```ssh-config
Host *.minivirt
  Include ~/.cache/minivirt/*/ssh-config
```

Start the VM, then log into it using SSH:

```shell
./minivirt.sh start foo --daemon --wait-for-ssh
ssh foo.minivirt
# ... do your thing ...
ssh foo.minivirt poweroff
```
