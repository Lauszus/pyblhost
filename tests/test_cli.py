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
import tempfile
from typing import Any
from unittest.mock import Mock, patch

import pytest
from typing_extensions import Self

from pyblhost.pyblhost import BlhostBase, cli


class MockBlhost:
    """Mock implementation of BlhostBase for testing CLI."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.logger = kwargs.get("logger", Mock(spec=logging.Logger))
        self.ping_result = True
        self.reset_result = True
        self.get_property_result = True
        self.upload_results = [50.0, 100.0, True]
        self.read_results = [50.0, 100.0, bytearray(b"test_data")]
        self.ping_args: list[dict[str, Any]] = []
        self.reset_args: list[dict[str, Any]] = []
        self.get_property_args: list[dict[str, Any]] = []
        self.upload_args: list[dict[str, Any]] = []
        self.read_args: list[dict[str, Any]] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def ping(self, timeout: float = 5.0) -> bool:
        self.ping_args.append({"timeout": timeout})
        return self.ping_result

    def reset(self, timeout: float = 5.0) -> bool:
        self.reset_args.append({"timeout": timeout})
        return self.reset_result

    def get_property(
        self,
        property_tag: BlhostBase.PropertyTag,
        memory_id: int = 0,
        timeout: float = 5.0,
        ping_repeat: int = 3,
    ) -> bool:
        self.get_property_args.append(
            {"property_tag": property_tag, "memory_id": memory_id, "timeout": timeout, "ping_repeat": ping_repeat}
        )
        return self.get_property_result

    def upload(
        self,
        binary_filename: str,
        start_address: int,
        erase_byte_count: int,
        timeout: float = 5.0,
        ping_repeat: int = 3,
        attempts: int = 1,
        reset: bool = True,
        assume_success: bool = False,
    ) -> Any:
        self.upload_args.append(
            {
                "binary_filename": binary_filename,
                "start_address": start_address,
                "erase_byte_count": erase_byte_count,
                "timeout": timeout,
                "ping_repeat": ping_repeat,
                "attempts": attempts,
                "reset": reset,
                "assume_success": assume_success,
            }
        )
        yield from self.upload_results

    def read(
        self,
        start_address: int,
        byte_count: int,
        timeout: float = 5.0,
        ping_repeat: int = 3,
    ) -> Any:
        self.read_args.append(
            {
                "start_address": start_address,
                "byte_count": byte_count,
                "timeout": timeout,
                "ping_repeat": ping_repeat,
            }
        )
        yield from self.read_results


class TestCLI:
    """Test cases for CLI function."""

    def test_cli_can_ping_success(self) -> None:
        """Test CLI ping command with CAN interface - success."""
        test_args = ["pyblhost", "can", "ping", "--tx-id", "0x123", "--rx-id", "0x456"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostCan", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        ping_args = mock_blhost.ping_args
        assert len(ping_args) == 1
        assert ping_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_can_ping_failure(self) -> None:
        """Test CLI ping command with CAN interface - failure."""
        test_args = ["pyblhost", "can", "ping", "--tx-id", "0x123", "--rx-id", "0x456"]

        mock_blhost = MockBlhost()
        mock_blhost.ping_result = False

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostCan", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 1

    def test_cli_serial_ping_success(self) -> None:
        """Test CLI ping command with serial interface - success."""
        test_args = ["pyblhost", "serial", "ping", "--port", "/dev/ttyUSB0"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        ping_args = mock_blhost.ping_args
        assert len(ping_args) == 1
        assert ping_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_reset_success(self) -> None:
        """Test CLI reset command - success."""
        test_args = ["pyblhost", "serial", "reset", "--port", "/dev/ttyUSB0"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        reset_args = mock_blhost.reset_args
        assert len(reset_args) == 1
        assert reset_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_reset_failure(self) -> None:
        """Test CLI reset command - failure."""
        test_args = ["pyblhost", "serial", "reset", "--port", "/dev/ttyUSB0"]

        mock_blhost = MockBlhost()
        mock_blhost.reset_result = False

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 1

    def test_cli_get_property_success(self) -> None:
        """Test CLI get_property command - success."""
        test_args = ["pyblhost", "serial", "get_property", "--port", "/dev/ttyUSB0", "--prop", "1"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        get_property_args = mock_blhost.get_property_args
        assert len(get_property_args) == 1
        assert get_property_args[0]["property_tag"] == BlhostBase.PropertyTag.BootloaderVersion
        assert get_property_args[0]["timeout"] == pytest.approx(1.0)
        assert get_property_args[0]["ping_repeat"] == 3

    def test_cli_get_property_hex_value(self) -> None:
        """Test CLI get_property command with hex property value."""
        test_args = ["pyblhost", "serial", "get_property", "--port", "/dev/ttyUSB0", "--prop", "0x1A"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        get_property_args = mock_blhost.get_property_args
        assert len(get_property_args) == 1
        assert get_property_args[0]["property_tag"] == BlhostBase.PropertyTag.ReliableUpdateStatus
        assert get_property_args[0]["timeout"] == pytest.approx(1.0)
        assert get_property_args[0]["ping_repeat"] == 3

    def test_cli_get_property_failure(self) -> None:
        """Test CLI get_property command - failure."""
        test_args = ["pyblhost", "serial", "get_property", "--port", "/dev/ttyUSB0", "--prop", "1"]

        mock_blhost = MockBlhost()
        mock_blhost.get_property_result = False

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 1

    def test_cli_upload_success(self) -> None:
        """Test CLI upload command - success."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test data")
            tmp_file.flush()

            test_args = [
                "pyblhost",
                "serial",
                "upload",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x1000",
                "--byte-count",
                "0x2000",
            ]

            mock_blhost = MockBlhost()

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli()

            assert exc_info.value.code == 0

            upload_args = mock_blhost.upload_args
            assert len(upload_args) == 1
            assert upload_args[0]["binary_filename"] == tmp_file.name
            assert upload_args[0]["start_address"] == 0x1000
            assert upload_args[0]["erase_byte_count"] == 0x2000
            assert upload_args[0]["timeout"] == pytest.approx(1.0)
            assert upload_args[0]["ping_repeat"] == 3
            assert upload_args[0]["attempts"] == 1
            assert upload_args[0]["reset"] is True
            assert upload_args[0]["assume_success"] is False

    def test_cli_upload_failure(self) -> None:
        """Test CLI upload command - failure."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test data")
            tmp_file.flush()

            test_args = [
                "pyblhost",
                "serial",
                "upload",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x1000",
                "--byte-count",
                "0x2000",
            ]

            mock_blhost = MockBlhost()
            mock_blhost.upload_results = [50.0, 100.0, False]

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli()

            assert exc_info.value.code == 1

    def test_cli_read_success(self) -> None:
        """Test CLI read command - success."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            test_args = [
                "pyblhost",
                "serial",
                "read",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x1000",
                "--byte-count",
                "0x100",
            ]

            mock_blhost = MockBlhost()

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
                patch("builtins.open", create=True) as mock_open,
            ):
                cli()

            assert exc_info.value.code == 0
            mock_open.assert_called()

            read_args = mock_blhost.read_args
            assert len(read_args) == 1
            assert read_args[0]["start_address"] == 0x1000
            assert read_args[0]["byte_count"] == 0x100
            assert read_args[0]["timeout"] == pytest.approx(1.0)
            assert read_args[0]["ping_repeat"] == 3

    def test_cli_read_failure(self) -> None:
        """Test CLI read command - failure."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            test_args = [
                "pyblhost",
                "serial",
                "read",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x1000",
                "--byte-count",
                "0x100",
            ]

            mock_blhost = MockBlhost()
            # Return empty list to simulate read failure without progress updates
            mock_blhost.read_results = []

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli()

            assert exc_info.value.code == 1

    def test_cli_missing_can_arguments(self) -> None:
        """Test CLI with missing CAN arguments."""
        test_args = ["pyblhost", "can", "ping"]

        with patch("sys.argv", test_args), pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 2  # argparse error exit code

    def test_cli_missing_serial_arguments(self) -> None:
        """Test CLI with missing serial arguments."""
        test_args = ["pyblhost", "serial", "ping"]

        with patch("sys.argv", test_args), pytest.raises(SystemExit) as exc_info:
            cli()

        assert exc_info.value.code == 2  # argparse error exit code

    def test_cli_missing_upload_arguments(self) -> None:
        """Test CLI upload with missing arguments."""
        test_args = ["pyblhost", "serial", "upload", "--port", "/dev/ttyUSB0"]

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", MockBlhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 2  # argparse error exit code

    def test_cli_missing_read_arguments(self) -> None:
        """Test CLI read with missing arguments."""
        test_args = ["pyblhost", "serial", "read", "--port", "/dev/ttyUSB0"]

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", MockBlhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 2  # argparse error exit code

    def test_cli_missing_get_property_arguments(self) -> None:
        """Test CLI get_property with missing arguments."""
        test_args = ["pyblhost", "serial", "get_property", "--port", "/dev/ttyUSB0"]

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", MockBlhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 2  # argparse error exit code

    def test_cli_invalid_property_value(self) -> None:
        """Test CLI get_property with invalid property value."""
        test_args = ["pyblhost", "serial", "get_property", "--port", "/dev/ttyUSB0", "--prop", "invalid"]

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", MockBlhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()
        assert exc_info.value.code == 2  # argparse error exit code

    def test_cli_can_extended_id(self) -> None:
        """Test CLI with CAN extended ID."""
        test_args = ["pyblhost", "can", "ping", "--tx-id", "0x123", "--rx-id", "0x456", "--extended-id", "1"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostCan", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        ping_args = mock_blhost.ping_args
        assert len(ping_args) == 1
        assert ping_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_can_custom_interface_and_channel(self) -> None:
        """Test CLI with custom CAN interface and channel."""
        test_args = [
            "pyblhost",
            "can",
            "ping",
            "--tx-id",
            "0x123",
            "--rx-id",
            "0x456",
            "--interface",
            "virtual",
            "--channel",
            "test_channel",
        ]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostCan", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        ping_args = mock_blhost.ping_args
        assert len(ping_args) == 1
        assert ping_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_custom_baudrate(self) -> None:
        """Test CLI with custom baudrate."""
        test_args = ["pyblhost", "serial", "ping", "--port", "/dev/ttyUSB0", "--baudrate", "115200"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        ping_args = mock_blhost.ping_args
        assert len(ping_args) == 1
        assert ping_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_custom_timeout_and_retries(self) -> None:
        """Test CLI with custom timeout and retries."""
        test_args = ["pyblhost", "serial", "ping", "--port", "/dev/ttyUSB0", "--timeout", "2.0", "--cmd-repeat", "5"]

        mock_blhost = MockBlhost()

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        ping_args = mock_blhost.ping_args
        assert len(ping_args) == 1
        assert ping_args[0]["timeout"] == pytest.approx(2.0)

    def test_cli_upload_no_reset(self) -> None:
        """Test CLI upload with no-reset flag."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test data")
            tmp_file.flush()

            test_args = [
                "pyblhost",
                "serial",
                "upload",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x1000",
                "--byte-count",
                "0x2000",
                "--no-reset",
            ]

            mock_blhost = MockBlhost()

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli()

            assert exc_info.value.code == 0

            upload_args = mock_blhost.upload_args
            assert len(upload_args) == 1
            assert upload_args[0]["binary_filename"] == tmp_file.name
            assert upload_args[0]["start_address"] == 0x1000
            assert upload_args[0]["erase_byte_count"] == 0x2000
            assert upload_args[0]["timeout"] == pytest.approx(1.0)
            assert upload_args[0]["ping_repeat"] == 3
            assert upload_args[0]["attempts"] == 1
            assert upload_args[0]["reset"] is False
            assert upload_args[0]["assume_success"] is False

    def test_cli_upload_assume_success(self) -> None:
        """Test CLI upload with assume-success flag."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test data")
            tmp_file.flush()

            test_args = [
                "pyblhost",
                "serial",
                "upload",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x1000",
                "--byte-count",
                "0x2000",
                "--assume-success",
            ]

            mock_blhost = MockBlhost()

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli()

            assert exc_info.value.code == 0

            upload_args = mock_blhost.upload_args
            assert len(upload_args) == 1
            assert upload_args[0]["binary_filename"] == tmp_file.name
            assert upload_args[0]["start_address"] == 0x1000
            assert upload_args[0]["erase_byte_count"] == 0x2000
            assert upload_args[0]["timeout"] == pytest.approx(1.0)
            assert upload_args[0]["ping_repeat"] == 3
            assert upload_args[0]["attempts"] == 1
            assert upload_args[0]["reset"] is True
            assert upload_args[0]["assume_success"] is True

    @patch("logging.getLogger")
    def test_cli_verbose_mode(self, mock_get_logger: Mock) -> None:
        """Test CLI with verbose flag."""
        test_args = ["pyblhost", "serial", "ping", "--port", "/dev/ttyUSB0", "--verbose"]

        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", MockBlhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        mock_logger.setLevel.assert_called_with(logging.DEBUG)
        assert exc_info.value.code == 0

    def test_cli_help(self) -> None:
        """Test CLI help flag."""
        test_args = ["pyblhost", "--help"]

        with patch("sys.argv", test_args), pytest.raises(SystemExit) as exc_info:
            cli()

        # Help should exit with code 0
        assert exc_info.value.code == 0

    def test_cli_version(self) -> None:
        """Test CLI version flag."""
        test_args = ["pyblhost", "--version"]

        with patch("sys.argv", test_args), pytest.raises(SystemExit) as exc_info:
            cli()

        # Version should exit with code 0
        assert exc_info.value.code == 0

    def test_cli_ping_multiple_retries_success_on_second_attempt(self) -> None:
        """Test CLI ping with multiple retries, success on second attempt."""
        test_args = ["pyblhost", "serial", "ping", "--port", "/dev/ttyUSB0", "--cmd-repeat", "2"]

        ping_args = []
        call_count = 0

        def mock_ping(timeout: float = 5.0) -> bool:
            nonlocal ping_args
            nonlocal call_count
            ping_args.append({"timeout": timeout})
            call_count += 1
            return call_count >= 2  # Fail on first call, succeed on second

        # Use Mock to properly mock the ping method
        mock_blhost = MockBlhost()
        mock_blhost.ping = Mock(side_effect=mock_ping)  # type: ignore[method-assign]

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 0

        assert len(ping_args) == 2  # Should have been called twice
        assert ping_args[0]["timeout"] == pytest.approx(1.0)

    def test_cli_reset_multiple_retries_all_fail(self) -> None:
        """Test CLI reset with multiple retries, all attempts fail."""
        test_args = ["pyblhost", "serial", "reset", "--port", "/dev/ttyUSB0", "--cmd-repeat", "2"]

        mock_blhost = MockBlhost()
        mock_blhost.reset_result = False

        with (
            patch("sys.argv", test_args),
            patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
            pytest.raises(SystemExit) as exc_info,
        ):
            cli()

        assert exc_info.value.code == 1

    def test_cli_address_parsing_decimal_and_hex(self) -> None:
        """Test CLI address parsing for decimal and hex values."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test data")
            tmp_file.flush()

            # Test with hex addresses
            test_args = [
                "pyblhost",
                "serial",
                "upload",
                "--port",
                "/dev/ttyUSB0",
                "--binary",
                tmp_file.name,
                "--start-address",
                "0x8000000",  # Hex
                "--byte-count",
                "4096",  # Decimal
            ]

            mock_blhost = MockBlhost()

            with (
                patch("sys.argv", test_args),
                patch("pyblhost.pyblhost.BlhostSerial", return_value=mock_blhost),
                pytest.raises(SystemExit) as exc_info,
            ):
                cli()

        assert exc_info.value.code == 0

        upload_args = mock_blhost.upload_args
        assert len(upload_args) == 1
        assert upload_args[0]["start_address"] == 0x8000000  # Hex parsed correctly
        assert upload_args[0]["erase_byte_count"] == 4096  # Decimal parsed correctly
        assert upload_args[0]["timeout"] == pytest.approx(1.0)
        assert upload_args[0]["ping_repeat"] == 3
        assert upload_args[0]["attempts"] == 1
        assert upload_args[0]["reset"] is True
        assert upload_args[0]["assume_success"] is False
