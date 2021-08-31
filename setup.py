#!/usr/bin/env python
#
# Python implemented of blhost used to communicate with the NXP MCUBOOT/KBOOT bootloader.
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

import re

from setuptools import setup, find_packages

with open('pyblhost/__init__.py', 'r') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        f.read(), re.MULTILINE).group(1)

with open('README.md', 'r') as f:
    long_description = f.read()

with open('requirements.txt', 'r') as f:
    install_requires = f.read().splitlines()

setup(
    name='pyblhost',
    version=version,
    packages=find_packages(),
    url='https://github.com/Lauszus/pyblhost',
    license='GPLv3',
    author='Kristian Sloth Lauszus',
    author_email='lauszus@gmail.com',
    description='Python implemented of blhost used to communicate with the NXP MCUBOOT/KBOOT bootloader',
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'pyblhost = pyblhost.pyblhost:cli',
        ],
    },
    python_requires='>=3.0',
    classifiers=(
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ),
)
