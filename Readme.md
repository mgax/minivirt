# Minivirt

VMs should be easy.

[![Discord](https://badgen.net/badge/icon/discord?icon=discord&label)](https://discord.gg/P72AGcEWHZ)

_Minivirt_ is a lightweight [QEMU][] manager that provides a Docker-like user experience. The default image is based on [Alpine Linux](https://alpinelinux.org/), which is tiny and fast: 50MB compressed disk image, boots to SSH in second(s).

[QEMU]: https://www.qemu.org/

## Installation

1. Install QEMU and other dependencies.
    * MacOS: `brew install qemu socat`
    * Debian: `apt install qemu-kvm qemu-utils qemu-efi-aarch64 socat`
    * Alpine: `apk add py3-pip qemu qemu-system-x86_64 qemu-img socat tar`
    * Arch: `pacman -S python-pip qemu-base socat`

1. Install _Minivirt_ and run a checkup.
    ```shell
    pip3 install minivirt
    miv doctor
    ```
1. Pull an image (or [build one yourself](#building-an-image)).
    ```shell
    miv remote add default https://f003.backblazeb2.com/file/minivirt
    miv pull default alpine-{arch} alpine  # {arch} is automatically replaced with your architecture.
    ```
1. Start a VM.
    ```shell
    miv run alpine
    ```

The `miv run` command will create an ephemeral VM and open an SSH session into it. When you exit the session, the VM is destroyed.

## How it works

The actual work of emulating virtual machines is done by QEMU. It runs in many environments, which means we can provide (mostly) the same features everywhere.

Virtual machines run as user processes, no root privileges necessary. The user does however need permissions for hardware virtualization (e.g. access to `/dev/kvm` on Linux).

It's possible to interact with the VM in three ways:
* Serial console: this is the default for `miv start`.
* Graphical display: enabled by the `--display` argument.
* SSH: `miv run` connects through SSH, using the [Vagrant well-known SSH key](https://github.com/hashicorp/vagrant/tree/main/keys). Also, `miv ssh` can shell into a running VM.

The QEMU VM is set up with [User Networking](https://wiki.qemu.org/Documentation/Networking#User_Networking_.28SLIRP.29), which doesn't interfere with the host's network stack, and the guest SSH port is forwarded to a random port on _localhost_. You can forward more ports with the `--port` option.

Minivirt manages [images](docs/Images.md), which are essentially read-only, reusable virtual machine qcow2 disks; and [VMs](docs/VMs.md), with their own [copy-on-write](https://en.wikibooks.org/wiki/QEMU/Images#Copy_on_write) disk, which uses the image disk as its backing file. Everything is stored in `~/.cache/minivirt/`.

### Doctor

The `miv doctor` command runs a checkup to help with troubleshooting. It checks to see if `qemu-system-{arch}`, `qemu-img`, `socat` and `tar` are installed, and if `/dev/kvm` is usable.

## Documentation

* [VMs](docs/VMs.md)
* [Images](docs/Images.md)
* [Database](docs/Database.md)
* [Development](docs/Development.md)

## Get in touch

For feedback, support, and contributions, visit:
* [The Discord server](https://discord.gg/P72AGcEWHZ).
* [Discussions](https://github.com/mgax/minivirt/discussions) on GitHub.
