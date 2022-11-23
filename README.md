# pyblhost

#### Developed by Kristian Sloth Lauszus, 2020-2022

The code is released under the GNU General Public License v3.0.
_________
[![PyPI](https://img.shields.io/pypi/v/pyblhost.svg)](https://pypi.org/project/pyblhost)
[![pyblhost CI](https://github.com/Lauszus/pyblhost/actions/workflows/build.yml/badge.svg)](https://github.com/Lauszus/pyblhost/actions/workflows/build.yml)

This is a Python implementation of [blhost](https://github.com/Lauszus/blhost) used to communicate with the [NXP MCUBOOT/KBOOT bootloader](https://www.nxp.com/design/software/development-software/mcuxpresso-software-and-tools-/mcuboot-mcu-bootloader-for-nxp-microcontrollers:MCUBOOT).

For now it only implements a subset of the blhost commands.

Currently serial and CAN-Bus interfaces are supported.

## Installation

```
pip install pyblhost
```

## Usage

### Python

See the [examples](examples) directory for Python examples.

### CLI

```
$ pyblhost -h
usage: pyblhost [-tx TX_ID] [-rx RX_ID] [-i INTERFACE] [-l CHANNEL] [-p PORT] [-h] [--version] [-B BINARY] [-s START_ADDRESS] [-c BYTE_COUNT] [-t TIMEOUT] [-r CMD_REPEAT] [-b BAUDRATE] {can,serial} {upload,read,ping,reset}

positional arguments:
  {can,serial}          Communicate with the target via either CAN or serial
  {upload,read,ping,reset}
                        upload: write BINARY to START_ADDRESS. Before writing it will erase the memory from START_ADDRESS to START_ADDRESS + BYTE_COUNT
                        read: read memory from START_ADDRESS to START_ADDRESS + BYTE_COUNT. the read data will be stored in BINARY
                        ping: send a ping command to the target and check for a response
                        reset: send a reset command to the target and check for a response

required CAN arguments:
  -tx TX_ID, --tx-id TX_ID
                        The TX ID (in hex) to use for CAN
  -rx RX_ID, --rx-id RX_ID
                        The RX ID (in hex) to use for CAN

optional CAN arguments:
  -i INTERFACE, --interface INTERFACE
                        The CAN-Bus interface to use (default "socketcan")
  -l CHANNEL, --channel CHANNEL
                        The CAN-Bus channel to use (default "can0")

required serial arguments:
  -p PORT, --port PORT  The port to use for serial

optional arguments:
  -h, --help            Show this help message and exit
  --version             Show program's version number and exit
  -B BINARY, --binary BINARY
                        The binary to upload or write memory into
  -s START_ADDRESS, --start-address START_ADDRESS
                        The address (in hex) to upload the binary at or read memory from
  -c BYTE_COUNT, --byte-count BYTE_COUNT
                        The number of bytes (in hex) to erase/read
  -t TIMEOUT, --timeout TIMEOUT
                        The time to wait in seconds for a response (default 1.0)
  -r CMD_REPEAT, --cmd-repeat CMD_REPEAT
                        The number of times to try to establish a connection (default 3)
  -b BAUDRATE, --baudrate BAUDRATE, --bitrate BAUDRATE
                        The baudrate/bitrate to use for serial/can (default 500000)
```

__Upload__

```
pyblhost can upload -tx 0x123 -rx 0x321 -B blink.bin -s 0x4C000 -c 0x34000
```

```
pyblhost serial upload -p /dev/ttyUSB0 -b 500000 -B blink.bin -s 0x4C000 -c 0x34000
```

__Read__

```
pyblhost can read -tx 0x123 -rx 0x321 -B memory.bin -s 0xC000 -c 0x34000
```

```
pyblhost serial read -p /dev/ttyUSB0 -b 500000 -B memory.bin -s 0xC000 -c 0x34000
```

__Ping__

```
pyblhost can ping -tx 0x123 -rx 0x321
```

```
pyblhost serial ping -p /dev/ttyUSB0 -b 500000
```

__Reset__

```
pyblhost can reset -tx 0x123 -rx 0x321
```

```
pyblhost serial reset -p /dev/ttyUSB0 -b 500000
```
