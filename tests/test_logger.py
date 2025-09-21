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

import io
import logging
import os
from unittest import mock

import pytest

from pyblhost.logger import (
    ColoredFormatter,
    EscapeCodes,
)


def test_init_default_values() -> None:
    """Test that the ColoredFormatter initializes with default values correctly."""
    formatter = ColoredFormatter()

    # Check default log colors
    assert formatter._log_colors == {
        "DEBUG": "light_blue",
        "INFO": "light_green",
        "WARNING": "light_yellow",
        "ERROR": "light_red",
        "CRITICAL": "bold_light_red",
    }


def test_init_custom_values() -> None:
    """Test that the ColoredFormatter initializes with custom values correctly."""
    custom_colors = {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }
    formatter = ColoredFormatter(fmt="%(message)s", force_color=True, log_colors=custom_colors)

    # Check that custom colors were set
    assert formatter._log_colors == custom_colors
    # Check that force_color was applied
    assert formatter._support_colors is True


def test_support_colors() -> None:
    """Test the support_colors method."""
    # Test with force_color=True
    assert ColoredFormatter.support_colors(force_color=True) is True

    # Test with environment variable
    with mock.patch.dict(os.environ, {"FORCE_COLOR": "1"}):
        assert ColoredFormatter.support_colors() is True

    with mock.patch.dict(os.environ, {"FORCE_COLOR": "0"}):
        assert ColoredFormatter.support_colors() is False

    with mock.patch.dict(os.environ, {"NO_COLOR": "1"}), mock.patch("sys.stdout.isatty", return_value=True):
        assert ColoredFormatter.support_colors() is False

    with mock.patch.dict(os.environ, {"NO_COLOR": "0"}), mock.patch("sys.stdout.isatty", return_value=True):
        assert ColoredFormatter.support_colors() is True

    # Test default behavior (depends on sys.stdout.isatty())
    with mock.patch("sys.stdout") as mock_stdout:
        # Test when isatty() returns True
        mock_stdout.isatty.return_value = True
        assert ColoredFormatter.support_colors() is True

        # Test when isatty() returns False
        mock_stdout.isatty.return_value = False
        assert ColoredFormatter.support_colors() is False

        # Test when isatty doesn't exist
        delattr(mock_stdout, "isatty")
        assert ColoredFormatter.support_colors() is False


def test_esc_method() -> None:
    """Test the escape code generation method."""
    assert ColoredFormatter.esc(0) == "\033[0m"
    assert ColoredFormatter.esc(1) == "\033[1m"
    assert ColoredFormatter.esc(1, 31) == "\033[1;31m"


def test_parse_colors() -> None:
    """Test the _parse_colors method."""
    formatter = ColoredFormatter(force_color=True)

    # Test parsing single color
    assert formatter._parse_colors("red") == formatter._escape_codes["red"]

    # Test parsing multiple colors
    assert formatter._parse_colors("bold,red") == formatter._escape_codes["bold"] + formatter._escape_codes["red"]

    # Test handling invalid color
    with pytest.raises(KeyError):
        formatter._parse_colors("invalid,red")


def test_escape_code_map() -> None:
    """Test the _escape_code_map method."""
    formatter = ColoredFormatter(force_color=True)

    # Test valid level name
    escapes = formatter._escape_code_map("INFO")
    assert "reset" in escapes
    assert "log_color" in escapes
    assert escapes["log_color"] == formatter._parse_colors("light_green")

    # Test invalid level name
    escapes = formatter._escape_code_map("UNKNOWN")
    assert "reset" in escapes
    assert "log_color" in escapes
    assert escapes["log_color"] == ""

    # Test with colors disabled
    formatter._support_colors = False
    escapes = formatter._escape_code_map("INFO")
    assert escapes["reset"] == ""
    assert escapes["log_color"] == ""


def test_format_message() -> None:
    """Test that messages are formatted correctly with color codes."""
    formatter = ColoredFormatter(fmt="[%(log_color)s%(levelname)s%(reset)s] %(msg)s", force_color=True)

    # Create a record
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Format the message
    result = formatter.formatMessage(record)

    # Check that color codes are included
    assert formatter._parse_colors("reset") in result
    assert formatter._parse_colors(formatter._log_colors[record.levelname]) in result
    assert "Test message" in result

    # Test with colors disabled
    formatter._support_colors = False
    result = formatter.formatMessage(record)

    # Check that color codes are not included
    assert formatter._parse_colors("reset") not in result
    assert formatter._parse_colors(formatter._log_colors[record.levelname]) not in result
    assert "Test message" in result


def test_formatter_integration() -> None:
    """Integration test for the ColoredFormatter using a StringIO stream."""
    # Setup a logger with our formatter
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.INFO)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)

    formatter = ColoredFormatter(fmt="%(log_color)s%(levelname)s%(reset)s: %(message)s", force_color=True)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Log some messages
    logger.info("This is an info message")
    logger.warning("This is a warning message")

    # Get the output
    output = stream.getvalue()

    # Verify the output contains the messages and color codes
    assert "This is an info message" in output
    assert "This is a warning message" in output
    assert formatter._parse_colors("reset") in output
    assert formatter._parse_colors(formatter._log_colors["INFO"]) in output
    assert formatter._parse_colors(formatter._log_colors["WARNING"]) in output


def test_color_text() -> None:
    """Test the EscapeCodes.color_text static method."""
    test_text = "Hello World"

    # Test with colors enabled (force_color=True)
    result = EscapeCodes.color_text(test_text, EscapeCodes.RED, force_color=True)
    expected = f"\033[{EscapeCodes.RED.value}m{test_text}\033[{EscapeCodes.RESET.value}m"
    assert result == expected

    # Test with different colors
    result = EscapeCodes.color_text(test_text, EscapeCodes.LIGHT_GREEN, force_color=True)
    expected = f"\033[{EscapeCodes.LIGHT_GREEN.value}m{test_text}\033[{EscapeCodes.RESET.value}m"
    assert result == expected

    # Test with bold
    result = EscapeCodes.color_text(test_text, EscapeCodes.BOLD, force_color=True)
    expected = f"\033[{EscapeCodes.BOLD.value}m{test_text}\033[{EscapeCodes.RESET.value}m"
    assert result == expected

    # Test with colors disabled (should return plain text)
    with mock.patch("sys.stdout.isatty", return_value=False):
        result = EscapeCodes.color_text(test_text, EscapeCodes.RED, force_color=False)
        assert result == test_text

    # Test with force_color=False but colors supported
    with mock.patch("sys.stdout.isatty", return_value=True):
        result = EscapeCodes.color_text(test_text, EscapeCodes.BLUE, force_color=False)
        expected = f"\033[{EscapeCodes.BLUE.value}m{test_text}\033[{EscapeCodes.RESET.value}m"
        assert result == expected
