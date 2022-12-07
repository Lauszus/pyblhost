#!/usr/bin/env python
#
# Python implementation of blhost used to communicate with the NXP MCUBOOT/KBOOT bootloader.
# Copyright (C) 2020-2022  Kristian Sloth Lauszus.
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

__version__ = '1.2.0'

__all__ = ['BlhostCan', 'BlhostSerial']

from .pyblhost import BlhostCan, BlhostSerial
