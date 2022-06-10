# MiniVirt – lightweight virtual machine manager

## Installation

```shell
python3 -m venv .venv
.venv/bin/pip3 install -r requirements/base.txt
./minivirt.sh doctor
```

## Usage

```shell
./minivirt.sh download-alpine
./minivirt.sh create alpine foo --disk=10G
./minivirt.sh -v bootstrap-alpine foo
./minivirt.sh start foo --display
# ... interact with the VM's display ...
./minivirt.sh destroy foo
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
