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
./minivirt.sh kill foo
```
