#!/usr/bin/env python
#
# Python implementation of blhost used to communicate with the NXP MCUBOOT/KBOOT bootloader.
# Copyright (C) 2020-2021  Kristian Sloth Lauszus.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Contact information
# -------------------
# Kristian Sloth Lauszus
# Web      :  https://www.lauszus.com
# e-mail   :  lauszus@gmail.com

import logging

from pyblhost import BlhostSerial


def main():
    # BlhostSerial specific arguments
    port, baudrate = '/dev/ttyUSB0', 500000

    # Create a logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(stream_handler)

    with BlhostSerial(port, baudrate, logger) as blhost:
        for i in range(3):  # Try 3 times
            if blhost.reset(timeout=1):  # Wait 1 second for a response
                logger.info('Ping responded in {} attempt(s)'.format(i + 1))
                exit(0)

        logger.error('Timed out waiting for ping response')
        exit(1)


if __name__ == '__main__':
    main()
