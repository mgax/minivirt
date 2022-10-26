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
