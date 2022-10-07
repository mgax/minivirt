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
    pip3 install minivirt --pre
    miv doctor
    ```
1. Pull an image and start a VM.
    ```shell
    miv remote add default https://f003.backblazeb2.com/file/minivirt
    miv pull default alpine-{arch} alpine  # {arch} is automatically replaced with your architecture.
    miv run alpine
    ```

The `miv run` command will create an ephemeral VM and open an SSH session into it. When you exit the session, the VM is destroyed.

## Under the hood

The actual work of emulating virtual machines is done by QEMU. It runs in many environments, which means we can provide (mostly) the same features everywhere.

Virtual machines run as user processes, no root privileges necessary. The user does however need permissions for hardware virtualization (e.g. access to `/dev/kvm` on Linux).

It's possible to interact with the VM in three ways:
* Serial console: this is the default for `miv start`.
* Graphical display: enabled by the `--display` argument.
* SSH: `miv run` connects through SSH, using the [Vagrant well-known SSH key](https://github.com/hashicorp/vagrant/tree/main/keys). Also, `miv ssh` can shell into a running VM.

The QEMU VM is set up with [User Networking](https://wiki.qemu.org/Documentation/Networking#User_Networking_.28SLIRP.29), which doesn't interfere with the host's network stack, and the guest SSH port is forwarded to a random port on _localhost_.

Minivirt manages [images](#images), which are essentially read-only, reusable virtual machine qcow2 disks; and [VMs](#persistent-vms), with their own [copy-on-write](https://en.wikibooks.org/wiki/QEMU/Images#Copy_on_write) disk, which uses the image disk as its backing file. Everything is stored in `~/.cache/minivirt/`.

### Doctor

The `miv doctor` command runs a checkup to help with troubleshooting. It checks to see if `qemu-system-{arch}`, `qemu-img`, `socat` and `tar` are installed, and if `/dev/kvm` is usable.

## Persistent VMs

Create a VM with the `create` command:
```shell
miv create alpine myvm
```

Start the VM with the terminal attached to its serial console:
```shell
miv start myvm
```

Gracefully stop the VM by sending an ACPI poweroff:
```shell
miv stop myvm
```

Destroy the VM to remove its disk image and other resources:
```shell
miv destroy myvm
```

Inspect the VMs:
```shell
miv ps
miv ps -a  # also shows stopped VMs
```

### Graphics

Start the VM in the background and connect a display to it:
```shell
miv create alpine myvm
miv start myvm --daemon --display
```

Log in as `root`, and run:

```shell
setup-xorg-base
apk add xfce4 xfce4-terminal dbus
startx
```

To make the screen bigger, right-click on the desktop, hover on _Applications_, then _Settings_, and click _Display_. Select another resolution like "1440x900" and click "apply".

## Images

_Minivirt_ maintains a database of images identified by their SHA256 checksum. They may have any number of tags.

Show images in the database:

```shell
% miv images
5446f671 1.4G ubuntu-22.04
84200bbd 115M alpine-3.15
8ad24d9f 1.4G ubuntu-20.04
c86a9115 114M alpine alpine-3.16
```

### Building an image

Minivirt can build images from _recipes_, which are YAML files, with a syntax inspired by [GitHub Actions workflows][]. Download any file from [the `/recipes` directory](recipes/) and run:

```shell
miv build alpine-3.16.yaml --tag alpine -v
```

The `-v` flag directs the output of the build (serial console or SSH) to stdout.

The image is now in the database:

```shell
miv run alpine
```

[GitHub Actions workflows]: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions

### Other image operations

Commit a VM as an image:

```shell
miv commit myvm myimage
```

Save the image as a TAR archive:

```shell
miv save myimage | gzip -1 > myimage.tgz
```

Later, load the image:

```shell
zcat myimage.tgz | miv load myimage
```

### Database maintenance

To make sure the images and VMs are consistent, run a database check:

```shell
miv fsck
```

To remove an image, first untag it. This only removes the tag, not the image itself.

```shell
miv untag myimage
```

The image is removed during prune:

```shell
miv prune
```

### Image repositories

Add a remote repository:

```shell
miv remote add default https://f003.backblazeb2.com/file/minivirt
```

Pull an image. `{arch}` will be interpolated to the machine architecture.

```shell
miv pull default alpine-{arch} alpine
```

To host an image repository, you need an object store (e.g. [Amazon S3](https://aws.amazon.com/s3/), [Backblaze B2](https://www.backblaze.com/b2/), [MinIO](https://min.io/), etc). Set the following environment variables:

* `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: authentication credentials.
* `AWS_ENDPOINT_URL` _(optional)_: if the object store is not hosted on the AWS public cloud, this should point to the appropriate endpoint.

The bucket name is taken from the last part of the remote's URL, e.g. `minivirt` for the default repository.

Run `miv push` to upload an image:

```shell
miv push default alpine-3.16 alpine-3.16-aarch64
```

## Development

1. Clone the repository:
    ```shell
    git clone https://github.com/mgax/minivirt
    cd minivirt
    ```

1. Create a virtualenv so you don't interfere with gobally-installed packages:
    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    ```

1. Install the repo in edit mode and development dependencies:
    ```shell
    pip install -e '.[devel]'
    ```

1. Run the test suite:
    ```shell
    pytest
    pytest --runslow  # if you're not in a hurry
    ```

### Python API

_Minivirt_ is written in Python and offers a straightforward API:

```python
from minivirt.cli import db

alpine = db.get_image('alpine')
myvm = VM.create(db, 'myvm', image=alpine, memory=512)
with myvm.run(wait_for_ssh=30):
    print(myvm.ssh('uname -a', capture=True))
```

### GitHub Actions self-hosted runners

Minivirt comes with a server that launches GitHub Actions runners when a workflow job is queued. Each runner is ephemeral and runs in its own VM.

1. Install extra dependencies:
    ```shell
    pip install -e minivirt[githubactions]
    ```

1. Build an actions runner image:
    ```shell
    miv build recipes/alpine-3.15.yaml --tag alpine-3.15 -v
    miv build recipes/ci-alpine.yaml --tag ci-alpine -v
    miv build recipes/githubactions-alpine.yaml --tag githubactions-alpine -v
    ```

1. Run the server. To interact with the GitHub API, it needs a [GitHub PAT][], and runs `git credentials fill` to retrieve it. It uses [ngrok][] to listen for webhook events; to avoid the ngrok session timing out, set a token in the `NGROK_AUTH_TOKEN` environment variable.
    ```shell
    miv -v githubactions serve githubactions-alpine {repo}
    ```

[GitHub PAT]: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token
[ngrok]: https://ngrok.com/

## Get in touch

For feedback, support, and contributions, visit:
* [The Discord server](https://discord.gg/P72AGcEWHZ).
* [Discussions](https://github.com/mgax/minivirt/discussions) on GitHub.
