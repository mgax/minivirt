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

### Requirements

MiniVirt runs on:

* Linux with x86_64 processor and hardware virutalization enabled.
* Mac OS with Apple M1 processor. Does not support nested virutalization.

### Dependencies

You'll need [qemu][], [python3][] and [socat][] installed.

[qemu]: https://www.qemu.org/
[python3]: https://www.python.org/
[socat]: http://www.dest-unreach.org/socat/

* MacOS: `brew install qemu socat`
* Debian: `apt install qemu-system-x86 qemu-utils socat`
* Alpine: `apk add py3-pip qemu qemu-system-x86_64 qemu-img socat tar git`

### Instructions

```shell
pip3 install git+https://github.com/mgax/minivirt
miv doctor  # run a diagnostic check
```

The images and VMs will be stored in `~/.cache/minivirt/`.

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

Gracefully stop a VM by sending a poweroff request:

```shell
miv stop foo
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

If you get unexpected errors, run a database check:

```shell
miv fsck
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

### Recipes

Minivirt can build images from recipes, which are YAML files, with a syntax inspired by Github Actions workflows.

```shell
miv build recipes/alpine-3.16.yaml --tag alpine-3.16-{arch} -v
```

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

Install extra dependencies:

```shell
pip install -e minivirt[githubactions]
```

The `miv githubactions build` command prepares an actions runner image:

```shell
miv build recipes/alpine-3.15.4.yaml --tag alpine-3.15 -v
miv build recipes/alpine-ci-base.yaml --tag alpine-ci-base -v
miv -v githubactions build alpine-ci-base githubactions
```

Minivirt comes with a webhook listener that waits for `workflow_job` events; each time a job is queued, the listener schedules an ephemeral runner VM that will receive the job.

The listener needs a Github PAT. It runs `git credentials fill` to retrieve the token.

```shell
miv -v githubactions serve githubactions {repo} --memory 2048 --concurrency 2
```

### Systemd

If you want to host an app in a VM, it's possible to set up a [systemd](https://systemd.io/) service. This command will generate a service [unit file](https://www.freedesktop.org/software/systemd/man/systemd.unit.html):

```
miv systemd vm-unit ci
```

Review the output and save it as `/etc/systemd/system/minivirt-ci.service`.

Then, you can run the app as a foreground command. The stdout/stderr output of the app process will be logged by systemd.

```
miv systemd command-unit ci RUNNER_ALLOW_RUNASROOT=yes /root/actions-runner/run.sh
```

Review the output and save it as `/etc/systemd/system/minivirt-ci-runner.service`.

Finally, start the systemd services:

```shell
sudo systemctl daemon-reload
sudo systemctl enable --now minivirt-ci
sudo systemctl enable --now minivirt-ci-runner
```

### Desktop environment

It's easy to install a graphic environment in Alpine:

```shell
miv remote add default https://f003.backblazeb2.com/file/minivirt
miv pull default 'alpine-3.15.4-{arch}' alpine  # '{arch}' is automatically replaced with your architecture.
miv create alpine foo
miv start foo --display
```

Then, log in as `root`, and run:

```shell
setup-xorg-base
apk add xfce4 xfce4-terminal dbus
startx
```

To make the screen bigger, right-click on the desktop, hover on _Applications_, then _Settings_, and click _Display_. Select another resolution like "1440x900" and click "apply".

WHen you're done, run `poweroff` in a shell, and the VM will shut down cleanly.

## Get in touch

[Discord server](https://discord.gg/P72AGcEWHZ)
