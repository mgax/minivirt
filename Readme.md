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

## Persistent VMs

The images and VMs are stored in `~/.cache/minivirt/`.

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

Commit a VM as an image:

```shell
miv commit myvm myimage
```

Save the image as a TAR archive:

```shell
miv save myimage | gzip -1 > ~/myimage.tgz
```

Later, load the image:

```shell
zcat ~/myimage.tgz | miv load myimage
```

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

To host an image repository, you need an S3-compatible object store (e.g. AWS S3, Backblaze B2). Set the following environment variables:

* `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: authentication credentials.
* `AWS_ENDPOINT_URL` _(optional)_: if the object store is not hosted on the AWS public cloud, this should point to the appropriate endpoint.

The bucket name is taken from the last part of the remote's URL, e.g. `minivirt` for the default repository.

Run `miv push` to upload an image:

```shell
miv push default alpine-3.16 alpine-3.16-aarch64
```

## Development

1. Create a virtualenv so you don't interfere with gobally-installed packages:
    ```shell
    python3 -m venv .venv
    source .venv/bin/activate
    ```

1. Install the repo in edit mode and development dependencies:
    ```shell
    pip3 install -e .
    pip3 install pytest
    ```

1. Run the test suite:
    ```shell
    pytest
    pytest --runslow  # if you're not in a hurry
    ```

### Recipes

Minivirt can build images from recipes, which are YAML files, with a syntax inspired by Github Actions workflows. [The _recipes_ directory](recipes/) contains some examples.

```shell
miv build recipes/alpine-3.16.yaml --tag alpine-3.16 -v
```

The `-v` flag directs the output of the build (serial console or SSH) to stdout.

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
