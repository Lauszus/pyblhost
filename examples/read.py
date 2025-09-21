#!/usr/bin/env python
#
# Python implementation of blhost used to communicate with the NXP MCUBOOT/KBOOT bootloader.
# Copyright (C) 2020-2025  Kristian Sloth Lauszus.
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

from __future__ import annotations

import logging
import sys

from pyblhost import BlhostCan


def main() -> None:
    # BlhostCan specific arguments
    tx_id, rx_id = 0x123, 0x321

    # Create a logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stream_handler)

    # Specify the binary write to, the start address to read from and the byte count to read
    binary = "memory.bin"
    start_address, byte_count = 0x0C000, 0x34000

    with BlhostCan(tx_id, rx_id, logger) as blhost:
        old_progress = None
        data = None
        for progress in blhost.read(start_address, byte_count, timeout=1):
            if not isinstance(progress, bytearray):
                # The progress is returned as a float, so round the value in order to not spam the console
                progress = round(progress)
                if progress != old_progress:
                    old_progress = progress
                    logger.info(f"Read memory progress: {progress} %")
            else:
                data = progress
        if data is None:
            logger.error("Reading memory failed")
            sys.exit(1)
        with open(binary, "wb") as f:
            f.write(data)
        logger.info("Reading memory succeeded")
        sys.exit(0)


if __name__ == "__main__":
    main()
