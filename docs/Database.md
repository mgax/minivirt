# Minivirt database

Minivirt stores images and VMs in a database, which is just a bunch of folders and files. By default it's located at `~/.cache/minivirt`, but it can be changed by setting `$MINIVIRT_DB_PATH`.

## Images

An image is an immutable snapshot of a virtual machine. It typically consists of a qcow2 disk image and a configuration file. It's identified by an `id` which is calculated based on its files using SHA256. The image files reside in a folder named `{db}/images/{id}`.

### Tags

An image may have tags, which are named references to the image. On disk they are implemented as symlinks to the image directory and are located at `{db}/images/{tag}`.

## VMs

A VM is an instance of a virtual machine. Each VM has a unique `name` and its files reside in a directory like `{db}/vms/{name}`.

Typically a VM will be derived from an image, which is referenced in `config.json` under the `"image"` key. The VMs's qcow2 disk will have the image's disk as backing file.

At runtime, a VM will create several files:
* `run.json` contains runtime data like the SSH TCP port.
* `ssh-config` is a ssh configuration file for the VM.
* `ssh-private-key` is the SSH identity key that can log into the VM.

## Remotes

The file `{db}/remotes.json` lists the remote repositories that are configured with the `miv remote` command.

## Cache

When `miv build` needs to download a file, it will save a copy in `{db}/cache`, to speed up future builds.
