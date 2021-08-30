# pyblhost

#### Developed by Kristian Sloth Lauszus, 2020-2021

The code is released under the GNU General Public License v3.0.
_________
[![PyPI](https://img.shields.io/pypi/v/pyblhost.svg)](https://pypi.org/project/pyblhost)
[![pyblhost CI](https://github.com/Lauszus/pyblhost/actions/workflows/build.yml/badge.svg)](https://github.com/Lauszus/pyblhost/actions/workflows/build.yml)

This is a Python implemented of [blhost](https://github.com/Lauszus/blhost) used to communicate with [NXP MCUBOOT/KBOOT bootloader](https://www.nxp.com/design/software/development-software/mcuxpresso-software-and-tools-/mcuboot-mcu-bootloader-for-nxp-microcontrollers:MCUBOOT).

For now it only implements a subset of the blhost commands.

Current UART and CAN-Bus interfaces are supported.

## Installation

```
pip install pyblhost
```

## Usage

### Python

See the [examples](examples) directory for Python examples.

### CLI

```
$ pyblhost --help
usage: pyblhost [-h] -i {can,serial} [-B BINARY] [-s START_ADDRESS] [-c BYTE_COUNT] [-t TIMEOUT] [-r CMD_REPEAT] [-tx TX_ID] [-rx RX_ID]
                [-p PORT] [-b BAUDRATE]
                {upload,read,ping,reset}

positional arguments:
  {upload,read,ping,reset}
                        Command to run. Either "upload", "read", "ping" or "reset"

optional arguments:
  -h, --help            show this help message and exit
  -i {can,serial}       The interface to use
  -B BINARY             The binary to upload
  -s START_ADDRESS      The address (in hex) to upload the binary at or read memory from
  -c BYTE_COUNT         The number of bytes (in hex) to erase/read
  -t TIMEOUT            The time to wait in seconds for a response
  -r CMD_REPEAT         The number of times to try to establish a connection
  -tx TX_ID             The TX ID (in hex) to use for CAN
  -rx RX_ID             The RX ID (in hex) to use for CAN
  -p PORT               The port to use for serial
  -b BAUDRATE           The baudrate to use for serial
```

__Upload__

```
pyblhost upload -i can -tx 0x123 -rx 0x321 -B blink.bin -s 0x4C000 -c 0x34000
```

```
pyblhost upload -i serial -p /dev/ttyUSB0 -b 500000 -B blink.bin -s 0x4C000 -c 0x34000
```

__Read__

```
pyblhost read -i can -tx 0x123 -rx 0x321 -B memory.bin -s 0xC000 -c 0x34000
```

```
pyblhost read -i serial -p /dev/ttyUSB0 -b 500000 -B memory.bin -s 0xC000 -c 0x34000
```

__Ping__

```
pyblhost ping -i can -tx 0x123 -rx 0x321
```

```
pyblhost ping -i serial -p /dev/ttyUSB0 -b 500000
```

__Reset__

```
pyblhost reset -i can -tx 0x123 -rx 0x321
```

```
pyblhost reset -i serial -p /dev/ttyUSB0 -b 500000
```
