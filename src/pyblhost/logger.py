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
import os
import sys
from enum import IntEnum
from typing import Any

from typing_extensions import override


class EscapeCodes(IntEnum):
    RESET = 0
    BOLD = 1
    THIN = 2

    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    PURPLE = 35
    CYAN = 36
    WHITE = 37
    LIGHT_BLACK = 90
    LIGHT_RED = 91
    LIGHT_GREEN = 92
    LIGHT_YELLOW = 93
    LIGHT_BLUE = 94
    LIGHT_PURPLE = 95
    LIGHT_CYAN = 96
    LIGHT_WHITE = 97

    @staticmethod
    def color_text(text: str, color: EscapeCodes, force_color: bool = False) -> str:
        """Returns the text wrapped in ANSI escape codes for the given color if supported."""
        if ColoredFormatter.support_colors(force_color):
            return f"{ColoredFormatter.esc(color)}{text}{ColoredFormatter.esc(EscapeCodes.RESET)}"
        return text


class ColoredRecord:
    """
    Wraps a LogRecord, adding escape codes to the internal dict.

    The internal dict is used when formatting the message (by the PercentStyle,
    StrFormatStyle, and StringTemplateStyle classes).
    """

    def __init__(self, record: logging.LogRecord, escapes: dict[str, str]) -> None:
        self.__dict__.update(record.__dict__)
        self.__dict__.update(escapes)


class ColoredFormatter(logging.Formatter):
    """Inspired by: https://github.com/borntyping/python-colorlog"""

    def __init__(
        self,
        fmt: str | None = None,
        force_color: bool = False,
        log_colors: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(fmt=fmt, **kwargs)

        # The default colors to use for the debug levels
        default_log_colors = {
            "DEBUG": "light_blue",
            "INFO": "light_green",
            "WARNING": "light_yellow",
            "ERROR": "light_red",
            "CRITICAL": "bold_light_red",
        }

        self._support_colors = self.support_colors(force_color)
        self._log_colors = log_colors if log_colors is not None else default_log_colors

        self._escape_codes = {
            "reset": self.esc(EscapeCodes.RESET),
            "bold": self.esc(EscapeCodes.BOLD),
            "thin": self.esc(EscapeCodes.THIN),
        }

        escape_codes_foreground = {
            "black": EscapeCodes.BLACK,
            "red": EscapeCodes.RED,
            "green": EscapeCodes.GREEN,
            "yellow": EscapeCodes.YELLOW,
            "blue": EscapeCodes.BLUE,
            "purple": EscapeCodes.PURPLE,
            "cyan": EscapeCodes.CYAN,
            "white": EscapeCodes.WHITE,
            "light_black": EscapeCodes.LIGHT_BLACK,
            "light_red": EscapeCodes.LIGHT_RED,
            "light_green": EscapeCodes.LIGHT_GREEN,
            "light_yellow": EscapeCodes.LIGHT_YELLOW,
            "light_blue": EscapeCodes.LIGHT_BLUE,
            "light_purple": EscapeCodes.LIGHT_PURPLE,
            "light_cyan": EscapeCodes.LIGHT_CYAN,
            "light_white": EscapeCodes.LIGHT_WHITE,
        }

        # Foreground without prefix
        for name, code in escape_codes_foreground.items():
            self._escape_codes[f"{name}"] = self.esc(code)
            self._escape_codes[f"bold_{name}"] = self.esc(1, code)
            self._escape_codes[f"thin_{name}"] = self.esc(2, code)

    @staticmethod
    def esc(*codes: int | EscapeCodes) -> str:
        """Returns an ANSI escape code string for the given format codes."""
        return "\033[" + ";".join(str(int(code)) for code in codes) + "m"

    def _parse_colors(self, string: str) -> str:
        """Return escape codes from a color sequence string."""
        return "".join(self._escape_codes[n] for n in string.split(",") if n)

    @staticmethod
    def support_colors(force_color: bool = False) -> bool:
        """Check if the formatter supports colors."""
        if force_color or os.environ.get("FORCE_COLOR", "0") == "1":
            return True

        if os.environ.get("NO_COLOR", "0") == "1":
            return False

        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    @override
    def formatMessage(self, record: logging.LogRecord) -> str:
        """Format a message from a record object."""
        escapes = self._escape_code_map(record.levelname)
        wrapper = ColoredRecord(record, escapes)
        return super().formatMessage(wrapper)  # type: ignore[arg-type]

    def _escape_code_map(self, levelname: str) -> dict[str, str]:
        """
        Build a map of keys to escape codes for use in message formatting.
        """
        if self._support_colors:
            color = self._log_colors.get(levelname, "")
            return {
                "reset": self._escape_codes["reset"],
                "log_color": self._parse_colors(color),
            }
        else:
            # If colors are not supported, return an empty map
            return {
                "reset": "",
                "log_color": "",
            }
