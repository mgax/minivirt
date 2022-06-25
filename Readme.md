# MiniVirt – lightweight virtual machine manager

## Motivation

Because VMs should be as easy as containers.

### Neat things you can do with MiniVirt

* Run a throwaway desktop environment.
* Host your own GitHub Actions runner, so you don't pay for actions minutes, and are in control of the runtime environment. This is how the MiniVirt CI is hosted because it needs `/dev/kvm`.
* Run a test suite for Ansible playbooks.

The default VM is based on [Alpine Linux](https://alpinelinux.org/), which is tiny (50MB compressed disk image) and fast (boots to SSH in under 3 seconds).

### So why not use containers instead?

* Features: you don't have control of the kernel so you can't e.g. mount filesystems or load kernel modules.
* Desktop: containers are meant to run headless. With a VM, you can use its emulated display to run a graphic environment.
* Isolation: the container [is not a security boundary](https://blog.aquasec.com/container-isolation).
* Nesting: it's possible to nest containers, but it involves giving the parent container elevated permissions. Nesting VMs maintains isolation.
* Diversity: run any operating system that you can install from an ISO image.

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
miv pull default 'alpine-3.15.4-{arch}' alpine  # '{arch}' is automatically replaced with your architecture.
miv create alpine foo
miv start foo --display
# ... interact with the VM ...
miv destroy foo
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

### VMs

Show VMs in the database:

```shell
miv ps -a
```

Forcibly stop a VM:

```shell
miv kill foo
```

Delete a VM and all its files:

```shell
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

## Extra

### Alpine

The `miv alpine` commands will automate the download and installation of Alpine Linux. That's how the _default_ images are created:

```shell
miv alpine download 3.15.4 alpine-iso
miv -v alpine install alpine-iso alpine-3.15.4 10G
```

### Image repositories

Any S3-compatible object store can serve as an image repository. The following environment variables are read:

* `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: authentication credentials.
* `AWS_ENDPOINT_URL` _(optional)_: if the object store is not hosted on the AWS public cloud, this should point to the appropriate endpoint.

The bucket name is taken from the last part of the remote's URL, e.g. `minivirt` for the default repository.

The `miv push` command uploads an image:

```shell
miv remote add default https://f003.backblazeb2.com/file/minivirt
miv push default alpine-3.15.4 alpine-3.15.4-aarch64
```

### GitHub Actions

The `miv ci` command prepares a self-hosted actions runner:

```shell
miv -v ci build alpine-3.15.4 actions-runner
```

Follow the [instructions to add a self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners/adding-self-hosted-runners#adding-a-self-hosted-runner-to-an-organization). At step 6, grab the token, and run:

```shell
miv -v ci setup-github-runner actions-runner {repo} {token}
```

`{repo}` is the repository URL, e.g. `https://github.com/mgax/minivirt`. `{token}` is the setup token generated by GitHub, e.g. `AAAGXYIPYAWWSLBDSG5JN2TCWSTBA`.

To start the runner, boot up the VM, then call `run.sh` in foreground:

```shell
miv start actions-runner --daemon --wait-for-ssh=30
ssh actions-runner.miv RUNNER_ALLOW_RUNASROOT=yes /root/actions-runner/run.sh
```
