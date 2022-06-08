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
./minivirt.sh start foo
./minivirt.sh console foo  # To exit the console, type ^].
./minivirt.sh kill foo
```

### SSH

Add these lines to your ssh config (`~/.ssh/config`):

```ssh-config
Host *.minivirt
  Include ~/.cache/minivirt/*/ssh-config
```

Start the VM, then connect to its console, and log in as root:

```shell
./minivirt.sh start foo
./minivirt.sh console foo
```

Inside the VM, set up an SSH server:

```shell
echo | setup-alpine -q
setup-sshd -k https://github.com/{username}.keys openssh
```

Then exit the console with `^]` (control-]). Now you can connect to the VM using SSH:

```shell
ssh foo.minivirt
```
