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

Minivirt can build images from _recipes_, which are YAML files, with a syntax inspired by [GitHub Actions workflows][]. Download any file from [the `/recipes` directory](../recipes/) and run:

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
