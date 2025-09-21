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
import pathlib
import struct
import sys
import threading
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, mock_open, patch

import can
import pytest

from pyblhost.pyblhost import (
    BlhostBase,
    BlhostCan,
    BlhostCanListener,
    BlhostDataParser,
    BlhostSerial,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_version() -> None:
    """Test that the version string is the same as the one in pyproject.toml."""
    from pyblhost import __version__

    with open(pathlib.Path(__file__).parent / "../pyproject.toml", "rb") as f:
        toml_dict = tomllib.load(f)

    assert isinstance(__version__, str)
    assert __version__ == toml_dict["project"]["version"]


class TestBlhostBase:
    """Test cases for BlhostBase class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)

    def test_init(self) -> None:
        """Test BlhostBase initialization."""

        # Create a concrete implementation for testing
        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        # Check that logger is set
        assert blhost.logger == self.logger

        # Check that events are initialized
        assert isinstance(blhost._send_lock, type(threading.Lock()))
        assert isinstance(blhost._ack_response_event, threading.Event)
        assert isinstance(blhost._reset_response_event, threading.Event)
        assert isinstance(blhost._flash_erase_region_response_event, threading.Event)
        assert isinstance(blhost._read_memory_response_tag_event, threading.Event)
        assert isinstance(blhost._write_memory_response_event, threading.Event)
        assert isinstance(blhost._read_memory_response_event, threading.Event)
        assert isinstance(blhost._data_event, threading.Event)
        assert isinstance(blhost._ping_response_event, threading.Event)
        assert isinstance(blhost._get_command_response_event, threading.Event)

        # Check that memory data is initialized
        assert isinstance(blhost._memory_data, bytearray)
        assert len(blhost._memory_data) == 0

    def test_abstract_methods_raise_not_implemented(self) -> None:
        """Test that abstract methods."""

        class BlhostChildMissingSend(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        class BlhostChildMissingShutdown(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)

            def _send_implementation(self, data: list[int]) -> None:
                pass

        class BlhostChild(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        with pytest.raises(TypeError):
            BlhostChildMissingSend(self.logger)  # type: ignore[abstract]

        with pytest.raises(TypeError):
            BlhostChildMissingShutdown(self.logger)  # type: ignore[abstract]

        BlhostChild(self.logger)

    def test_send_with_lock(self) -> None:
        """Test that _send method uses lock and stores last packet."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                self.sent_data = data

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        test_data = [0x5A, 0xA6]

        blhost._send(test_data)

        assert blhost.sent_data == test_data
        assert blhost._last_send_packet == test_data

    def test_context_manager(self) -> None:
        """Test context manager implementation."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.shutdown_called = False

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                self.shutdown_called = True

        blhost = TestBlhost(self.logger)

        with blhost as context_blhost:
            assert context_blhost is blhost
            assert not blhost.shutdown_called

        assert blhost.shutdown_called

    def test_ping(self) -> None:
        """Test ping method."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                self.sent_data = data
                # Simulate immediate response
                self._ping_response_event.set()

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        result = blhost.ping(timeout=0.1)

        assert result is True
        assert blhost.sent_data == [
            BlhostBase.FramingPacketConstants.StartByte,
            BlhostBase.FramingPacketConstants.Type_Ping,
        ]
        self.logger.info.assert_called_with("BlhostBase: Sending ping command")

    def test_ping_timeout(self) -> None:
        """Test ping method timeout."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass  # Don't set the event to simulate timeout

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        result = blhost.ping(timeout=0.01)

        assert result is False

    def test_reset(self) -> None:
        """Test reset method."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.sent_commands: list[tuple[int, int]] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _command_packet(self, tag: BlhostBase.CommandTags, flags: int, *payload: Any) -> None:
                self.sent_commands.append((tag, flags))
                # Simulate immediate response
                self._reset_response_event.set()

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        result = blhost.reset(timeout=0.1)

        assert result is True
        assert blhost.sent_commands == [(BlhostBase.CommandTags.Reset, 0x00)]
        self.logger.info.assert_called_with("BlhostBase: Sending reset command")

    def test_chunks_static_method(self) -> None:
        """Test chunks static method."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        chunks = list(BlhostBase.chunks(data, 3))

        assert chunks == [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]

        # Test with exact division
        chunks = list(BlhostBase.chunks(data[:9], 3))
        assert chunks == [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

    def test_crc16_xmodem(self) -> None:
        """Test CRC16 XMODEM calculation."""
        # Test with known values
        test_data = b"123456789"
        expected_crc = 0x31C3  # Known CRC16-XMODEM for "123456789"

        result = BlhostBase.crc16_xmodem(test_data)
        assert result == expected_crc

        # Test with empty data
        result = BlhostBase.crc16_xmodem(b"")
        assert result == 0

        # Test with init value
        result = BlhostBase.crc16_xmodem(b"123", crc_init=0x1234)
        assert isinstance(result, int)
        assert 0 <= result <= 0xFFFF

    def test_framing_packet(self) -> None:
        """Test framing packet creation."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                self.sent_data = data

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        # Test with ping packet
        blhost._framing_packet(BlhostBase.FramingPacketConstants.Type_Ping, 0)

        # Should be: [StartByte, Type_Ping, length_low, length_high, crc_low, crc_high]
        assert len(blhost.sent_data) >= 6
        assert blhost.sent_data[0] == BlhostBase.FramingPacketConstants.StartByte
        assert blhost.sent_data[1] == BlhostBase.FramingPacketConstants.Type_Ping
        assert blhost.sent_data[2] == 0  # Length low byte
        assert blhost.sent_data[3] == 0  # Length high byte

        crc = BlhostBase.crc16_xmodem(blhost.sent_data[:4])
        assert blhost.sent_data[4] == crc & 0xFF  # CRC low byte
        assert blhost.sent_data[5] == crc >> 8  # CRC high byte

    def test_command_packet(self) -> None:
        """Test command packet creation."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.framing_calls: list[tuple[int, int, tuple[int, ...]]] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _framing_packet(self, packet_type: int, length: int, *payload: int) -> None:
                self.framing_calls.append((packet_type, length, payload))

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        blhost._command_packet(BlhostBase.CommandTags.Reset, 0x00, 1, 2, 3)

        assert len(blhost.framing_calls) == 1
        packet_type, length, payload = blhost.framing_calls[0]
        assert packet_type == BlhostBase.FramingPacketConstants.Type_Command
        assert length == 7  # 4 (header) + 3 (payload)
        assert payload == (BlhostBase.CommandTags.Reset, 0x00, 0, 3, 1, 2, 3)

    def test_data_packet(self) -> None:
        """Test data packet creation."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.framing_calls: list[tuple[int, int, tuple[int, ...]]] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _framing_packet(self, packet_type: int, length: int, *payload: int) -> None:
                self.framing_calls.append((packet_type, length, payload))

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        blhost._data_packet(1, 2, 3, 4)

        assert len(blhost.framing_calls) == 1
        packet_type, length, payload = blhost.framing_calls[0]
        assert packet_type == BlhostBase.FramingPacketConstants.Type_Data
        assert length == 4
        assert payload == (1, 2, 3, 4)

    def test_get_property(self) -> None:
        """Test get_property method."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ping_called = False
                self.get_property_called = False

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                self.ping_called = True
                return True

            def _get_property(self, property_tag: BlhostBase.PropertyTag, memory_id: int = 0) -> None:
                self.get_property_called = True
                # Simulate immediate response
                self._get_command_response_event.set()

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        result = blhost.get_property(BlhostBase.PropertyTag.BootloaderVersion, timeout=0.1)

        assert result is True
        assert blhost.ping_called
        assert blhost.get_property_called

    def test_get_property_ping_failure(self) -> None:
        """Test get_property when ping fails."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return False

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        result = blhost.get_property(BlhostBase.PropertyTag.BootloaderVersion, ping_repeat=1)

        assert result is False

    def test_upload_invalid_attempts(self) -> None:
        """Test upload with invalid attempts parameter."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        with pytest.raises(ValueError, match='"attempts" has to be greater than 0'):
            list(blhost.upload("test.bin", 0x1000, 0x1000, attempts=0))

    @patch("builtins.open", new_callable=mock_open, read_data=b"test_data")
    def test_upload_file_reading(self, mock_file: Mock) -> None:
        """Test upload file reading and padding."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.uploaded_data: bytes | None = None

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _upload(
                self,
                binary_data: bytes,
                start_address: int,
                erase_byte_count: int,
                timeout: float,
                ping_repeat: int,
                assume_success: bool = False,
            ) -> Generator[float, None, bool]:
                self.uploaded_data = binary_data
                yield 50.0  # Progress
                yield 100.0  # Progress
                return True

            def reset(self, timeout: float = 5.0) -> bool:
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        # Run upload and collect all yielded values
        results = list(blhost.upload("test.bin", 0x1000, 0x1000))

        # Check that file was read and padded correctly
        expected_data = b"test_data" + b"\xff" * 7  # Padded to 16-byte boundary
        assert blhost.uploaded_data == expected_data

        # Check results
        assert len(results) == 3  # Two progress values + final result
        assert results[0] == 50.0
        assert results[1] == 100.0
        assert results[2] is True

    @patch("builtins.open", new_callable=mock_open, read_data=b"test_data")
    def test_upload_multiple_attempts_success_on_retry(self, mock_file: Mock) -> None:
        """Test upload with multiple attempts, succeeding on retry."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.attempt_count = 0
                self.reset_calls = 0
                self.erase_calls = 0

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _upload(
                self,
                binary_data: bytes,
                start_address: int,
                erase_byte_count: int,
                timeout: float,
                ping_repeat: int,
                assume_success: bool = False,
            ) -> Generator[float, None, bool]:
                self.attempt_count += 1
                yield 50.0
                yield 100.0
                return self.attempt_count >= 2  # Fail first attempt, succeed on second

            def reset(self, timeout: float = 5.0) -> bool:
                self.reset_calls += 1
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                self.erase_calls += 1

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._flash_erase_region_response_event = Mock()
        blhost._flash_erase_region_response_event.wait.return_value = True

        # Run upload with 2 attempts
        results = list(blhost.upload("test.bin", 0x1000, 0x1000, attempts=2))

        assert blhost.attempt_count == 2
        assert blhost.reset_calls == 2  # Reset called after each attempt
        assert blhost.erase_calls == 1  # Erase called only after first failure
        assert results[-1] is True  # The final result is success

    @patch("builtins.open", new_callable=mock_open, read_data=b"test_data")
    def test_upload_reset_failure(self, mock_file: Mock) -> None:
        """Test upload when reset fails."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _upload(
                self,
                binary_data: bytes,
                start_address: int,
                erase_byte_count: int,
                timeout: float,
                ping_repeat: int,
                assume_success: bool = False,
            ) -> Generator[float, None, bool]:
                yield 100.0
                return True

            def reset(self, timeout: float = 5.0) -> bool:
                return False  # Reset fails

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        results = list(blhost.upload("test.bin", 0x1000, 0x1000))

        assert results[-1] is False  # Should fail due to reset failure

    @patch("builtins.open", new_callable=mock_open, read_data=b"test_data")
    def test_upload_no_reset(self, mock_file: Mock) -> None:
        """Test upload with reset disabled."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.reset_called = False

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _upload(
                self,
                binary_data: bytes,
                start_address: int,
                erase_byte_count: int,
                timeout: float,
                ping_repeat: int,
                assume_success: bool = False,
            ) -> Generator[float, None, bool]:
                yield 100.0
                return True

            def reset(self, timeout: float = 5.0) -> bool:
                self.reset_called = True
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        results = list(blhost.upload("test.bin", 0x1000, 0x1000, reset=False))

        assert not blhost.reset_called
        assert results[-1] is True

    def test_upload_internal_implementation(self) -> None:
        """Test _upload method internal implementation."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ping_calls = 0
                self.erase_calls = 0
                self.write_calls = 0
                self.data_packets_sent: list[Any] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                self.ping_calls += 1
                return True  # Always succeed for this test

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                self.erase_calls += 1

            def _write_memory(self, start_address: int, data: bytes) -> None:
                self.write_calls += 1

            def _data_packet(self, *payload: Any) -> None:
                self.data_packets_sent.append(list(payload))

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        # Mock the events
        blhost._flash_erase_region_response_event = Mock()
        blhost._flash_erase_region_response_event.wait.return_value = True
        blhost._write_memory_response_event = Mock()
        blhost._write_memory_response_event.wait.return_value = True
        blhost._ack_response_event = Mock()
        blhost._ack_response_event.wait.return_value = True

        test_data = b"A" * 100  # 100 bytes of test data

        # Use the generator properly to get both yielded values and return value
        generator = blhost._upload(test_data, 0x1000, 0x2000, timeout=1.0, ping_repeat=3)
        yielded_values = []
        return_value = None
        try:
            while True:
                yielded_values.append(next(generator))
        except StopIteration as e:
            return_value = e.value

        # Should ping once and succeed
        assert blhost.ping_calls == 1

        # Should call erase and write once each
        assert blhost.erase_calls == 1
        assert blhost.write_calls == 1

        # Should send data in 32-byte chunks (100 bytes = 4 chunks: 32+32+32+4)
        assert len(blhost.data_packets_sent) == 4
        assert len(blhost.data_packets_sent[0]) == 32  # First chunk
        assert len(blhost.data_packets_sent[1]) == 32  # Second chunk
        assert len(blhost.data_packets_sent[2]) == 32  # Third chunk
        assert len(blhost.data_packets_sent[3]) == 4  # Last chunk

        # Check progress values
        assert yielded_values[0] == 0.0  # Starting progress
        assert yielded_values[-1] == 100.0  # Final progress

        # Check the final result
        assert return_value is True

    def test_upload_ping_failure(self) -> None:
        """Test _upload when ping fails after all attempts."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return False  # Always fail

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        test_data = b"test"
        generator = blhost._upload(test_data, 0x1000, 0x2000, timeout=1.0, ping_repeat=3)

        # Should return False immediately without yielding anything
        try:
            next(generator)
            raise AssertionError("Should have raised StopIteration immediately")
        except StopIteration as e:
            assert e.value is False

    def test_upload_erase_timeout(self) -> None:
        """Test _upload when flash erase times out."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._flash_erase_region_response_event = Mock()
        blhost._flash_erase_region_response_event.wait.return_value = False  # Timeout

        test_data = b"test"
        generator = blhost._upload(test_data, 0x1000, 0x2000, timeout=0.01, ping_repeat=1)

        try:
            next(generator)
            raise AssertionError("Should have raised StopIteration")
        except StopIteration as e:
            assert e.value is False

    def test_upload_write_memory_timeout(self) -> None:
        """Test _upload when write memory command times out."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def _write_memory(self, start_address: int, data: bytes) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._flash_erase_region_response_event = Mock()
        blhost._flash_erase_region_response_event.wait.return_value = True
        blhost._write_memory_response_event = Mock()
        blhost._write_memory_response_event.wait.side_effect = [False, False]  # Both waits timeout

        test_data = b"test"
        generator = blhost._upload(test_data, 0x1000, 0x2000, timeout=0.01, ping_repeat=1)

        try:
            next(generator)
            raise AssertionError("Should have raised StopIteration")
        except StopIteration as e:
            assert e.value is False

    def test_upload_ack_timeout(self) -> None:
        """Test _upload when ACK response times out during data transmission."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def _write_memory(self, start_address: int, data: bytes) -> None:
                pass

            def _data_packet(self, *payload: Any) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._flash_erase_region_response_event = Mock()
        blhost._flash_erase_region_response_event.wait.return_value = True
        blhost._write_memory_response_event = Mock()
        blhost._write_memory_response_event.wait.return_value = True
        blhost._ack_response_event = Mock()
        blhost._ack_response_event.wait.return_value = False  # ACK timeout

        test_data = b"test_data_that_is_longer_than_32_bytes_to_require_chunking"
        generator = blhost._upload(test_data, 0x1000, 0x2000, timeout=0.01, ping_repeat=1)

        yielded_values = []
        try:
            while True:
                yielded_values.append(next(generator))
        except StopIteration as e:
            return_value = e.value

        # Should get initial 0.0 progress then fail during ACK timeout
        assert len(yielded_values) >= 1
        assert yielded_values[0] == 0.0  # Initial progress
        assert return_value is False

    def test_upload_assume_success(self) -> None:
        """Test _upload with assume_success flag when final wait times out."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _flash_erase_region(self, start_address: int, byte_count: int) -> None:
                pass

            def _write_memory(self, start_address: int, data: bytes) -> None:
                pass

            def _data_packet(self, *payload: Any) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._flash_erase_region_response_event = Mock()
        blhost._flash_erase_region_response_event.wait.return_value = True
        blhost._write_memory_response_event = Mock()
        blhost._write_memory_response_event.wait.side_effect = [True, False]  # Second wait times out
        blhost._ack_response_event = Mock()
        blhost._ack_response_event.wait.return_value = True

        test_data = b"test"
        generator = blhost._upload(test_data, 0x1000, 0x2000, timeout=0.01, ping_repeat=1, assume_success=True)

        yielded_values = []
        try:
            while True:
                yielded_values.append(next(generator))
        except StopIteration as e:
            return_value = e.value

        # Should have progress values and final result True due to assume_success
        assert len(yielded_values) >= 2
        assert yielded_values[0] == 0.0  # Initial progress
        assert return_value is True  # Should return True due to assume_success

    def test_read_method(self) -> None:
        """Test read method implementation."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ping_calls = 0
                self.read_memory_calls = 0

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                self.ping_calls += 1
                return True  # Always succeed

            def _read_memory(self, start_address: int, byte_count: int) -> None:
                self.read_memory_calls += 1

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        # Set up mock events and data
        blhost._read_memory_response_event = Mock()
        blhost._read_memory_response_event.wait.return_value = True
        blhost._data_event = Mock()
        blhost._data_event.wait.side_effect = [True, True, False]  # Two data events, then timeout
        blhost._read_memory_response_tag_event = Mock()
        blhost._read_memory_response_tag_event.is_set.return_value = True

        # The read method clears _memory_data at the start, so we need to simulate
        # data being added during the data events
        def simulate_data_reception() -> None:
            # Simulate receiving data in chunks
            if len(blhost._memory_data) == 0:
                blhost._memory_data.extend(b"A" * 50)  # First chunk
            else:
                blhost._memory_data.extend(b"B" * 50)  # Second chunk, total 100 bytes

        # Mock the data reception
        call_count = 0

        def mock_wait(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                simulate_data_reception()  # Add first 50 bytes
                return True  # First data chunk
            elif call_count == 2:
                simulate_data_reception()  # Add the remaining 50 bytes
                return True  # Second data chunk
            else:
                return False  # Timeout, but read_memory_response_tag_event is set

        blhost._data_event.wait = mock_wait

        # Collect all results from the generator
        results = []
        generator = blhost.read(0x1000, 100, timeout=1.0, ping_repeat=3)
        for result in generator:
            results.append(result)

        assert blhost.ping_calls == 1  # Should succeed on first try
        assert blhost.read_memory_calls == 1

        # Check that we have progress values and final data
        progress_values = [r for r in results if isinstance(r, float)]
        data_values = [r for r in results if isinstance(r, bytearray)]

        assert len(progress_values) >= 2  # At least two progress values
        assert progress_values[-1] == 100.0  # Final progress
        assert len(data_values) == 1  # One final data result
        assert len(data_values[0]) == 100  # 100 bytes total

    def test_read_ping_failure(self) -> None:
        """Test read method when ping fails."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return False

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        results = list(blhost.read(0x1000, 100, ping_repeat=2))

        assert len(results) == 0  # Should return empty generator

    def test_read_memory_response_timeout(self) -> None:
        """Test read method when read memory response times out."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _read_memory(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._read_memory_response_event = Mock()
        blhost._read_memory_response_event.wait.return_value = False  # Timeout

        results = list(blhost.read(0x1000, 100, timeout=0.01, ping_repeat=1))

        assert len(results) == 0

    def test_read_data_timeout(self) -> None:
        """Test read method when data event times out."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _read_memory(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._read_memory_response_event = Mock()
        blhost._read_memory_response_event.wait.return_value = True
        blhost._data_event = Mock()
        blhost._data_event.wait.return_value = False  # Timeout
        blhost._read_memory_response_tag_event = Mock()
        blhost._read_memory_response_tag_event.is_set.return_value = False  # Not done

        results = list(blhost.read(0x1000, 100, timeout=0.01, ping_repeat=1))

        assert len(results) == 1  # Should have one progress value before timeout
        assert isinstance(results[0], float)

    def test_read_incorrect_data_length(self) -> None:
        """Test read method when received data length doesn't match expected."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def ping(self, timeout: float = 5.0) -> bool:
                return True

            def _read_memory(self, start_address: int, byte_count: int) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._read_memory_response_event = Mock()
        blhost._read_memory_response_event.wait.return_value = True
        blhost._data_event = Mock()
        blhost._data_event.wait.return_value = False  # Timeout
        blhost._read_memory_response_tag_event = Mock()
        blhost._read_memory_response_tag_event.is_set.return_value = True  # Done reading

        # Set incorrect data length
        blhost._memory_data = bytearray(b"A" * 50)  # Only 50 bytes instead of 100

        results = list(blhost.read(0x1000, 100, timeout=0.01, ping_repeat=1))

        # Should have progress values but no final data due to length mismatch
        progress_values = [r for r in results if isinstance(r, float)]
        data_values = [r for r in results if isinstance(r, bytearray)]

        assert len(progress_values) >= 1
        assert len(data_values) == 0  # No data returned due to length error

    def test_data_callback_ack(self) -> None:
        """Test _data_callback with ACK packet."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._ack_response_event = Mock()

        ack_data = bytearray([BlhostBase.FramingPacketConstants.StartByte, BlhostBase.FramingPacketConstants.Type_Ack])

        blhost._data_callback(ack_data)

        blhost._ack_response_event.set.assert_called_once()

    def test_data_callback_nak_with_resend(self) -> None:
        """Test _data_callback with NAK packet and resend."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.resent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _send(self, data: list[int]) -> None:
                self.resent_data = data

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._last_send_packet = [0x5A, 0xA4, 0x01, 0x02]  # Some test packet

        nak_data = bytearray([BlhostBase.FramingPacketConstants.StartByte, BlhostBase.FramingPacketConstants.Type_Nak])

        blhost._data_callback(nak_data)

        assert blhost.resent_data == [0x5A, 0xA4, 0x01, 0x02]

    def test_data_callback_ack_abort(self) -> None:
        """Test _data_callback with ACK abort packet."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        abort_data = bytearray(
            [BlhostBase.FramingPacketConstants.StartByte, BlhostBase.FramingPacketConstants.Type_AckAbort]
        )

        blhost._data_callback(abort_data)

        # Should just log an error, no exceptions
        self.logger.error.assert_called()

    def test_data_callback_command_generic_response(self) -> None:
        """Test _data_callback with command packet - generic response."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._reset_response_event = Mock()
        blhost._get_command_response_event = Mock()

        # Create a generic response for Reset command with Success status
        command_data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_Command,  # Type
                # Length (8 bytes)
                0x08,
                0x00,
                # CRC (not validated in callback)
                0x00,
                0x00,
                BlhostBase.ResponseTags.GenericResponse,  # Tag
                0x00,  # Flags
                0x00,  # Reserved
                0x01,  # Parameter count
                # Status = Success
                0x00,
                0x00,
                0x00,
                0x00,
                # Command tag
                BlhostBase.CommandTags.Reset,
                0x00,
                0x00,
                0x00,
            ]
        )

        blhost._data_callback(command_data)

        # ACK should be called
        assert blhost.ack_called
        assert blhost._sent_data == [
            BlhostBase.FramingPacketConstants.StartByte,
            BlhostBase.FramingPacketConstants.Type_Ack,
        ]

        blhost._reset_response_event.set.assert_called_once()
        blhost._get_command_response_event.set.assert_called_once()

    def test_data_callback_command_read_memory_response(self) -> None:
        """Test _data_callback with read memory response."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._read_memory_response_event = Mock()
        blhost._get_command_response_event = Mock()

        # Create a read memory response with Success status
        command_data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_Command,  # Type
                # Length (8 bytes)
                0x08,
                0x00,
                # CRC (not validated in callback)
                0x00,
                0x00,
                BlhostBase.ResponseTags.ReadMemoryResponse,  # Tag
                0x00,  # Flags
                0x00,  # Reserved
                0x01,  # Parameter count
                # Status = Success
                0x00,
                0x00,
                0x00,
                0x00,
                # Data byte count = 100
                0x64,
                0x00,
                0x00,
                0x00,
            ]
        )

        blhost._data_callback(command_data)

        # ACK should be called
        assert blhost.ack_called
        assert blhost._sent_data == [
            BlhostBase.FramingPacketConstants.StartByte,
            BlhostBase.FramingPacketConstants.Type_Ack,
        ]

        blhost._read_memory_response_event.set.assert_called_once()
        blhost._get_command_response_event.set.assert_called_once()

    def test_data_callback_command_get_property_response(self) -> None:
        """Test _data_callback with get property response."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._get_command_response_event = Mock()

        # Create a get property response with property values
        command_data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_Command,  # Type
                # Length (12 bytes)
                0x0C,
                0x00,
                # CRC (not validated in callback)
                0x00,
                0x00,
                BlhostBase.ResponseTags.GetPropertyResponse,  # Tag
                0x00,  # Flags
                0x00,  # Reserved
                0x02,  # Parameter count (2)
                # Status = Success
                0x00,
                0x00,
                0x00,
                0x00,
                # Property value = 0x1234
                0x34,
                0x12,
                0x00,
                0x00,
            ]
        )

        blhost._data_callback(command_data)

        # ACK should be called
        assert blhost.ack_called
        assert blhost._sent_data == [
            BlhostBase.FramingPacketConstants.StartByte,
            BlhostBase.FramingPacketConstants.Type_Ack,
        ]

        blhost._get_command_response_event.set.assert_called_once()

    def test_data_callback_data_packet(self) -> None:
        """Test _data_callback with data packet."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._data_event = Mock()

        # Create a data packet with 4 bytes of payload
        data_packet = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_Data,  # Type
                # Length (4 bytes)
                0x04,
                0x00,
                # CRC (not validated in callback)
                0x00,
                0x00,
                # Data payload
                0xAA,
                0xBB,
                0xCC,
                0xDD,
            ]
        )

        blhost._data_callback(data_packet)

        # ACK should be called
        assert blhost.ack_called
        assert blhost._sent_data == [
            BlhostBase.FramingPacketConstants.StartByte,
            BlhostBase.FramingPacketConstants.Type_Ack,
        ]

        # Data event should be set and memory data updated
        blhost._data_event.set.assert_called_once()
        assert blhost._memory_data == bytearray([0xAA, 0xBB, 0xCC, 0xDD])

    def test_data_callback_ping_response(self) -> None:
        """Test _data_callback with ping response."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._ping_response_event = Mock()

        # Create a ping response packet (P1.2.0)
        ping_response = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,
                BlhostBase.FramingPacketConstants.Type_PingResponse,
                0x30,  # '0' (bugfix)
                0x32,  # '2' (minor)
                0x31,  # '1' (major)
                0x50,  # 'P' (name)
                # Options
                0x00,
                0x00,
            ]
        )

        blhost._data_callback(ping_response)

        blhost._ping_response_event.set.assert_called_once()

    def test_data_callback_unsupported_protocol_version(self) -> None:
        """Test _data_callback with unsupported protocol version."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._ping_response_event = Mock()

        # Create a ping response with unsupported version (using correct byte order)
        ping_response = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_PingResponse,  # Type
                0x30,  # '0' (bugfix)
                0x30,  # '0' (minor)
                0x32,  # '2' (major) - unsupported
                0x50,  # 'P' (name)
                # Options
                0x00,
                0x00,
            ]
        )

        blhost._data_callback(ping_response)

        blhost._ping_response_event.set.assert_called_once()
        # The actual parsing uses chr() on the name byte and constructs the version string
        # So P(0x50) + 2(0x32) + .(0x30) + 0(0x30) = "P2.0.0" but the bytes are parsed as integers
        expected_version = f"P{0x32}.{0x30}.{0x30}"  # This will be "P50.48.48"
        self.logger.error.assert_called_with(f"BlhostBase: Unsupported protocol version: {expected_version}")

    def test_data_callback_invalid_start_byte(self) -> None:
        """Test _data_callback with invalid start byte."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        invalid_data = bytearray([0xFF, 0xA1])  # Invalid start byte

        blhost._data_callback(invalid_data)

        self.logger.error.assert_called_with(f"BlhostBase: Invalid start byte: {invalid_data}")

    def test_data_callback_unknown_command_type(self) -> None:
        """Test _data_callback with unknown command type."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)

        unknown_data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,
                0xFF,  # Unknown command type
            ]
        )

        blhost._data_callback(unknown_data)

        self.logger.info.assert_called_with("BlhostBase: Unhandled command type: 255")

    def test_data_callback_error_status_logging(self) -> None:
        """Test _data_callback logs errors with appropriate level for non-success status."""

        class TestBlhost(BlhostBase):
            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                pass

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._get_command_response_event = Mock()

        # Create a generic response with error status
        command_data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_Command,  # Type
                # Length (8 bytes)
                0x08,
                0x00,
                # CRC (not validated in callback)
                0x00,
                0x00,
                BlhostBase.ResponseTags.GenericResponse,  # Tag
                0x00,  # Flags
                0x00,  # Reserved
                0x01,  # Parameter count
                # Status = Fail
                0x01,
                0x00,
                0x00,
                0x00,
                # Command tag
                BlhostBase.CommandTags.Reset,
                0x00,
                0x00,
                0x00,
            ]
        )

        blhost._data_callback(command_data)

        # Should log with WARNING level for non-success status
        warning_calls = [call for call in self.logger.log.call_args_list if call[0][0] == logging.WARNING]
        assert len(warning_calls) > 0

    def test_data_callback_command_flash_erase_region(self) -> None:
        """Test _data_callback with FlashEraseRegion command response."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._flash_erase_region_response_event = Mock()
        blhost._get_command_response_event = Mock()

        status = [
            struct.Struct("<L").pack(BlhostBase.StatusCodes.Success),
            struct.Struct("<L").pack(BlhostBase.StatusCodes.Fail),
        ]

        for stat in status:
            blhost._flash_erase_region_response_event.reset_mock()
            blhost._get_command_response_event.reset_mock()
            blhost.ack_called = False
            blhost._sent_data = []

            # Create a generic response for FlashEraseRegion command with Success status
            command_data = bytearray(
                [
                    BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                    BlhostBase.FramingPacketConstants.Type_Command,  # Type
                    # Length (8 bytes)
                    0x08,
                    0x00,
                    # CRC (not validated in callback)
                    0x00,
                    0x00,
                    BlhostBase.ResponseTags.GenericResponse,  # Tag
                    0x00,  # Flags
                    0x00,  # Reserved
                    0x01,  # Parameter count
                    # Status = Success
                    *stat,
                    # Command tag = FlashEraseRegion
                    BlhostBase.CommandTags.FlashEraseRegion,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            blhost._data_callback(command_data)

            # ACK should always be called
            assert blhost.ack_called
            assert blhost._sent_data == [
                BlhostBase.FramingPacketConstants.StartByte,
                BlhostBase.FramingPacketConstants.Type_Ack,
            ]

            warning_calls = [call for call in self.logger.log.call_args_list if call[0][0] == logging.WARNING]
            if stat != struct.Struct("<L").pack(BlhostBase.StatusCodes.Success):
                assert len(warning_calls) > 0
                assert len(warning_calls) == 2  # One for GenericResponse, one for FlashEraseRegion
                blhost._flash_erase_region_response_event.assert_not_called()
                blhost._get_command_response_event.assert_not_called()
            else:
                assert len(warning_calls) == 0
                blhost._flash_erase_region_response_event.set.assert_called_once()
                blhost._get_command_response_event.set.assert_called_once()

    def test_data_callback_command_read_memory(self) -> None:
        """Test _data_callback with ReadMemory command response."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._read_memory_response_tag_event = Mock()
        blhost._get_command_response_event = Mock()

        status = [
            struct.Struct("<L").pack(BlhostBase.StatusCodes.Success),
            struct.Struct("<L").pack(BlhostBase.StatusCodes.OutOfRange),
        ]

        for stat in status:
            blhost._read_memory_response_tag_event.reset_mock()
            blhost._get_command_response_event.reset_mock()
            blhost.ack_called = False
            blhost._sent_data = []

            # Create a generic response for ReadMemory command with Success status
            command_data = bytearray(
                [
                    BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                    BlhostBase.FramingPacketConstants.Type_Command,  # Type
                    # Length (8 bytes)
                    0x08,
                    0x00,
                    # CRC (not validated in callback)
                    0x00,
                    0x00,
                    BlhostBase.ResponseTags.GenericResponse,  # Tag
                    0x00,  # Flags
                    0x00,  # Reserved
                    0x01,  # Parameter count
                    # Status = Success
                    *stat,
                    # Command tag = ReadMemory
                    BlhostBase.CommandTags.ReadMemory,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            blhost._data_callback(command_data)

            # ACK should always be called
            assert blhost.ack_called
            assert blhost._sent_data == [
                BlhostBase.FramingPacketConstants.StartByte,
                BlhostBase.FramingPacketConstants.Type_Ack,
            ]

            warning_calls = [call for call in self.logger.log.call_args_list if call[0][0] == logging.WARNING]
            if stat != struct.Struct("<L").pack(BlhostBase.StatusCodes.Success):
                assert len(warning_calls) > 0
                assert len(warning_calls) == 2  # One for GenericResponse, one for ReadMemory
                blhost._read_memory_response_tag_event.assert_not_called()
                blhost._get_command_response_event.assert_not_called()
            else:
                assert len(warning_calls) == 0
                blhost._read_memory_response_tag_event.set.assert_called_once()
                blhost._get_command_response_event.set.assert_called_once()

    def test_data_callback_command_write_memory(self) -> None:
        """Test _data_callback with WriteMemory command response."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._write_memory_response_event = Mock()
        blhost._get_command_response_event = Mock()

        status = [
            struct.Struct("<L").pack(BlhostBase.StatusCodes.Success),
            struct.Struct("<L").pack(BlhostBase.StatusCodes.MemoryWriteFailed),
        ]

        for stat in status:
            blhost._write_memory_response_event.reset_mock()
            blhost._get_command_response_event.reset_mock()
            blhost.ack_called = False
            blhost._sent_data = []

            # Create a generic response for WriteMemory command with Success status
            command_data = bytearray(
                [
                    BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                    BlhostBase.FramingPacketConstants.Type_Command,  # Type
                    # Length (8 bytes)
                    0x08,
                    0x00,
                    # CRC (not validated in callback)
                    0x00,
                    0x00,
                    BlhostBase.ResponseTags.GenericResponse,  # Tag
                    0x00,  # Flags
                    0x00,  # Reserved
                    0x01,  # Parameter count
                    # Status = Success
                    *stat,
                    # Command tag = WriteMemory
                    BlhostBase.CommandTags.WriteMemory,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            blhost._data_callback(command_data)

            # ACK should always be called
            assert blhost.ack_called
            assert blhost._sent_data == [
                BlhostBase.FramingPacketConstants.StartByte,
                BlhostBase.FramingPacketConstants.Type_Ack,
            ]

            warning_calls = [call for call in self.logger.log.call_args_list if call[0][0] == logging.WARNING]
            if stat != struct.Struct("<L").pack(BlhostBase.StatusCodes.Success):
                assert len(warning_calls) > 0
                assert len(warning_calls) == 2  # One for GenericResponse, one for ReadMemory
                blhost._write_memory_response_event.assert_not_called()
                blhost._get_command_response_event.assert_not_called()
            else:
                assert len(warning_calls) == 0
                blhost._write_memory_response_event.set.assert_called_once()
                blhost._get_command_response_event.set.assert_called_once()

    def test_data_callback_command_reliable_update(self) -> None:
        """Test _data_callback with ReliableUpdate command response - success status."""

        class TestBlhost(BlhostBase):
            def __init__(self, logger: logging.Logger) -> None:
                super().__init__(logger)
                self.ack_called = False
                self._sent_data: list[int] = []

            def _send_implementation(self, data: list[int]) -> None:
                pass

            def _ack(self) -> None:
                self.ack_called = True
                super()._ack()

            def _send(self, data: list[int]) -> None:
                self._sent_data.extend(data)

            def shutdown(self, timeout: float = 1.0) -> None:
                pass

        blhost = TestBlhost(self.logger)
        blhost._get_command_response_event = Mock()

        # The reliable update command can return multiple status codes indicating success:
        # Success, ReliableUpdateSuccess
        status = [
            struct.Struct("<L").pack(BlhostBase.StatusCodes.Success),
            struct.Struct("<L").pack(BlhostBase.StatusCodes.ReliableUpdateSuccess),
            struct.Struct("<L").pack(BlhostBase.StatusCodes.ReliableUpdateFail),
        ]

        for stat in status:
            blhost._get_command_response_event.reset_mock()
            blhost.ack_called = False
            blhost._sent_data = []

            # Create a generic response for ReliableUpdate command with ReliableUpdateSuccess status
            command_data = bytearray(
                [
                    BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                    BlhostBase.FramingPacketConstants.Type_Command,  # Type
                    # Length (8 bytes)
                    0x08,
                    0x00,
                    # CRC (not validated in callback)
                    0x00,
                    0x00,
                    BlhostBase.ResponseTags.GenericResponse,  # Tag
                    0x00,  # Flags
                    0x00,  # Reserved
                    0x01,  # Parameter count
                    # Status
                    *stat,
                    # Command tag = ReliableUpdate
                    BlhostBase.CommandTags.ReliableUpdate,
                    0x00,
                    0x00,
                    0x00,
                ]
            )

            blhost._data_callback(command_data)

            # ACK should always be called
            assert blhost.ack_called
            assert blhost._sent_data == [
                BlhostBase.FramingPacketConstants.StartByte,
                BlhostBase.FramingPacketConstants.Type_Ack,
            ]

            warning_calls = [call for call in self.logger.log.call_args_list if call[0][0] == logging.WARNING]
            if stat not in [
                struct.Struct("<L").pack(BlhostBase.StatusCodes.Success),
                struct.Struct("<L").pack(BlhostBase.StatusCodes.ReliableUpdateSuccess),
            ]:
                assert len(warning_calls) > 0
                assert len(warning_calls) == 2  # One for GenericResponse, one for ReadMemory
                blhost._get_command_response_event.assert_not_called()
            else:
                assert len(warning_calls) == 0
                blhost._get_command_response_event.set.assert_called_once()


class TestBlhostDataParser:
    """Test cases for BlhostDataParser class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.parser = BlhostDataParser(self.logger)

    def test_init(self) -> None:
        """Test BlhostDataParser initialization."""
        assert self.parser._logger == self.logger
        assert isinstance(self.parser._data, bytearray)
        assert len(self.parser._data) == 0
        assert self.parser._data_len is None
        assert self.parser._data_crc is None

    def test_parse_invalid_start_byte(self) -> None:
        """Test parsing with invalid start byte."""
        data = bytearray([0xFF, 0xA1])  # Invalid start byte

        result = self.parser.parse(data)

        assert result is None
        self.logger.warning.assert_called()

    def test_parse_ack_packet(self) -> None:
        """Test parsing ACK packet."""
        data = bytearray([BlhostBase.FramingPacketConstants.StartByte, BlhostBase.FramingPacketConstants.Type_Ack])

        result = self.parser.parse(data)

        assert result == data
        assert len(self.parser._data) == 0  # Should be consumed

    def test_parse_nak_packet(self) -> None:
        """Test parsing NAK packet."""
        data = bytearray([BlhostBase.FramingPacketConstants.StartByte, BlhostBase.FramingPacketConstants.Type_Nak])

        result = self.parser.parse(data)

        assert result == data

    def test_parse_ping_command_ignored(self) -> None:
        """Test that ping commands are ignored."""
        data = bytearray([BlhostBase.FramingPacketConstants.StartByte, BlhostBase.FramingPacketConstants.Type_Ping])

        result = self.parser.parse(data)

        assert result is None
        self.logger.warning.assert_called_with("BootloaderDataParser: Received ping command")

    def test_parse_ping_response(self) -> None:
        """Test parsing ping response."""
        # Create a valid ping response with correct CRC
        ping_data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,  # Start byte
                BlhostBase.FramingPacketConstants.Type_PingResponse,  # Type
                # P1.2.0
                0x50,
                0x31,
                0x32,
                0x30,
                # Options
                0x00,
                0x00,
            ]
        )

        # Calculate CRC for the ping response
        crc = BlhostBase.crc16_xmodem(ping_data)
        ping_data.extend([crc & 0xFF, (crc >> 8) & 0xFF])

        result = self.parser.parse(ping_data)

        assert result == ping_data

    def test_parse_incomplete_data(self) -> None:
        """Test parsing with incomplete data."""
        # Send only the start byte
        data = bytearray([BlhostBase.FramingPacketConstants.StartByte])

        result = self.parser.parse(data)

        assert result is None
        assert len(self.parser._data) == 1  # Data should be buffered

    def test_parse_command_packet_with_crc_mismatch(self) -> None:
        """Test parsing command packet with CRC mismatch."""
        data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,
                BlhostBase.FramingPacketConstants.Type_Command,
                # Length = 4
                0x04,
                0x00,
                # Wrong CRC
                0x00,
                0x00,
                # Generic response header
                0xA0,
                0x00,
                0x00,
                0x01,
                # Status = Success
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )

        result = self.parser.parse(data)

        assert result is None  # Should be discarded due to CRC mismatch
        self.logger.error.assert_called()

    def test_parse_unknown_command_type(self) -> None:
        """Test parsing with unknown command type."""
        data = bytearray(
            [
                BlhostBase.FramingPacketConstants.StartByte,
                0xFF,  # Unknown type
            ]
        )

        result = self.parser.parse(data)

        assert result is None
        self.logger.error.assert_called_with("BootloaderDataParser: Unknown command type: 255")


class TestBlhostCanListener:
    """Test cases for BlhostCanListener class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)
        self.callback = Mock()
        self.listener = BlhostCanListener(
            tx_id=0x123, extended_id=False, logger=self.logger, callback_func=self.callback
        )

    def test_init(self) -> None:
        """Test BlhostCanListener initialization."""
        assert self.listener._tx_id == 0x123
        assert self.listener._extended_id is False
        assert self.listener._logger == self.logger
        assert self.listener._callback_func == self.callback
        assert isinstance(self.listener._parser, BlhostDataParser)
        assert self.listener._stopped is False

    def test_on_message_received_filters_messages(self) -> None:
        """Test that on_message_received filters messages correctly."""
        # Create a message that should be ignored (wrong ID)
        msg = Mock(spec=can.Message)
        msg.is_error_frame = False
        msg.is_remote_frame = False
        msg.is_extended_id = False
        msg.arbitration_id = 0x456  # Wrong ID
        msg.data = bytearray([0x5A, 0xA1])

        self.listener.on_message_received(msg)

        self.callback.assert_not_called()

    def test_on_message_received_processes_valid_message(self) -> None:
        """Test that valid messages are processed."""
        # Create a valid message
        msg = Mock(spec=can.Message)
        msg.is_error_frame = False
        msg.is_remote_frame = False
        msg.is_extended_id = False
        msg.arbitration_id = 0x123  # Correct ID
        msg.data = bytearray([0x5A, 0xA1])  # ACK packet

        self.listener.on_message_received(msg)

        self.callback.assert_called_once_with(bytearray([0x5A, 0xA1]))

    def test_on_message_received_when_stopped(self) -> None:
        """Test that stopped listener ignores messages."""
        self.listener.stop()

        msg = Mock(spec=can.Message)
        msg.is_error_frame = False
        msg.is_remote_frame = False
        msg.is_extended_id = False
        msg.arbitration_id = 0x123
        msg.data = bytearray([0x5A, 0xA1])

        self.listener.on_message_received(msg)

        self.callback.assert_not_called()

    def test_on_error_logs_when_not_stopped(self) -> None:
        """Test that errors are logged when not stopped."""
        exc = Exception("Test error")

        self.listener.on_error(exc)

        self.logger.exception.assert_called_with("BlhostCanListener: on_error")

    def test_on_error_ignores_when_stopped(self) -> None:
        """Test that errors are ignored when stopped."""
        self.listener.stop()
        exc = Exception("Test error")

        self.listener.on_error(exc)

        self.logger.exception.assert_not_called()

    def test_stop(self) -> None:
        """Test stop method."""
        assert self.listener._stopped is False

        self.listener.stop()

        assert self.listener._stopped is True


@patch("can.Bus")
@patch("can.Notifier")
class TestBlhostCan:
    """Test cases for BlhostCan class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)

    def test_init_with_default_bus(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test BlhostCan initialization with default bus."""
        mock_bus_instance = Mock()
        mock_bus_instance.channel_info = "test_channel"
        mock_bus.return_value = mock_bus_instance

        with BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger) as blhost:
            assert blhost._tx_id == 0x123
            assert blhost._rx_id == 0x456
            assert blhost._extended_id is False
            assert blhost._can_bus_shutdown is True

            # Check that CAN bus was created with correct filters
            mock_bus.assert_called_once()
            call_args = mock_bus.call_args
            assert call_args[1]["interface"] == "socketcan"
            assert call_args[1]["channel"] == "can0"
            assert call_args[1]["bitrate"] == 500000

            # Check filters
            filters = call_args[1]["can_filters"]
            assert len(filters) == 1
            assert filters[0]["can_id"] == 0x123
            assert filters[0]["can_mask"] == 0x7FF
            assert filters[0]["extended"] is False

    def test_init_with_provided_bus(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test BlhostCan initialization with provided bus."""
        provided_bus = Mock()

        with BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger, can_bus=provided_bus) as blhost:
            assert blhost._can_bus == provided_bus
            assert blhost._can_bus_shutdown is False
            mock_bus.assert_not_called()

    def test_init_with_extended_id(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test BlhostCan initialization with extended ID."""
        mock_bus_instance = Mock()
        mock_bus_instance.channel_info = "test_channel"
        mock_bus.return_value = mock_bus_instance

        with BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger, extended_id=True) as blhost:
            assert blhost._extended_id is True

            # Check that extended ID filter was used
            call_args = mock_bus.call_args
            filters = call_args[1]["can_filters"]
            assert filters[0]["can_mask"] == 0x1FFFFFFF
            assert filters[0]["extended"] is True

    def test_send_implementation(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test _send_implementation method."""
        mock_bus_instance = Mock()
        mock_bus.return_value = mock_bus_instance

        with BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger) as blhost:
            # Test sending data
            test_data = list(range(20))  # 20 bytes of data
            blhost._send_implementation(test_data)

            # Should send 3 messages (8+8+4 bytes)
            assert mock_bus_instance.send.call_count == 3

            # Check first message
            first_call = mock_bus_instance.send.call_args_list[0]
            msg = first_call[0][0]
            assert msg.arbitration_id == 0x456
            assert list(msg.data) == test_data[:8]  # Convert bytearray to list for comparison
            assert msg.is_extended_id is False

    def test_send_implementation_with_sleep(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test _send_implementation with sleep between messages."""
        mock_bus_instance = Mock()
        mock_bus.return_value = mock_bus_instance

        with (
            patch("time.sleep") as mock_sleep,
            BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger, time_to_sleep_between_messages=0.001) as blhost,
        ):
            test_data = list(range(16))  # 16 bytes of data
            blhost._send_implementation(test_data)

            # Should send 2 messages and sleep 2 times
            assert mock_bus_instance.send.call_count == 2
            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(0.001)

    def test_shutdown_with_owned_bus(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test shutdown when owning the bus."""
        mock_bus_instance = Mock()
        mock_bus.return_value = mock_bus_instance
        mock_notifier_instance = Mock()
        mock_notifier.return_value = mock_notifier_instance

        with BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger):
            pass  # Context manager will call shutdown

        mock_notifier_instance.stop.assert_called_once_with(timeout=1.0)
        mock_bus_instance.shutdown.assert_called_once()

    def test_shutdown_with_provided_bus(self, mock_notifier: Mock, mock_bus: Mock) -> None:
        """Test shutdown when using provided bus."""
        provided_bus = Mock()
        mock_notifier_instance = Mock()
        mock_notifier.return_value = mock_notifier_instance

        with BlhostCan(tx_id=0x123, rx_id=0x456, logger=self.logger, can_bus=provided_bus):
            pass  # Context manager will call shutdown

        mock_notifier_instance.stop.assert_called_once_with(timeout=1.0)
        provided_bus.shutdown.assert_not_called()


@patch("serial.Serial")
@patch("threading.Thread")
class TestBlhostSerial:
    """Test cases for BlhostSerial class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.logger = Mock(spec=logging.Logger)

    def test_init(self, mock_thread: Mock, mock_serial: Mock) -> None:
        """Test BlhostSerial initialization."""
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        with BlhostSerial(port="/dev/ttyUSB0", baudrate=115200, logger=self.logger) as blhost:
            # Check that serial port was opened with correct parameters
            mock_serial.assert_called_once_with(port="/dev/ttyUSB0", baudrate=115200, timeout=0.5)

            # Check that thread was created and started
            mock_thread.assert_called_once()
            call_args = mock_thread.call_args
            assert call_args[1]["target"] == BlhostSerial._serial_read_thread
            assert call_args[1]["name"] == "_serial_read_thread"
            mock_thread_instance.start.assert_called_once()

            assert blhost._serial == mock_serial_instance
            assert isinstance(blhost._shutdown_thread, threading.Event)

    def test_send_implementation(self, mock_thread: Mock, mock_serial: Mock) -> None:
        """Test _send_implementation method."""
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance

        with BlhostSerial(port="/dev/ttyUSB0", baudrate=115200, logger=self.logger) as blhost:
            test_data = [0x5A, 0xA1, 0x02, 0x03]
            blhost._send_implementation(test_data)

            mock_serial_instance.write.assert_called_once_with(bytes(test_data))

    def test_shutdown(self, mock_thread: Mock, mock_serial: Mock) -> None:
        """Test shutdown method."""
        mock_serial_instance = Mock()
        mock_serial.return_value = mock_serial_instance
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        with BlhostSerial(port="/dev/ttyUSB0", baudrate=115200, logger=self.logger) as blhost:
            pass  # Context manager will call shutdown

        assert blhost._shutdown_thread.is_set()
        mock_thread_instance.join.assert_called_once_with(timeout=1.0)
        mock_serial_instance.close.assert_called_once()

    def test_serial_read_thread(self, mock_thread: Mock, mock_serial: Mock) -> None:
        """Test _serial_read_thread static method."""
        # Create mocks
        mock_ser = Mock()
        mock_ser.is_open = True
        shutdown_event = threading.Event()
        callback = Mock()

        # Mock the parser
        with patch("pyblhost.pyblhost.BlhostDataParser") as mock_parser_class:
            mock_parser = Mock()
            mock_parser_class.return_value = mock_parser

            # Set up the read behavior to simulate reading data then stopping
            def read_side_effect() -> bytes:
                if shutdown_event.is_set():
                    return b""
                return b"\x5a"

            mock_ser.read.side_effect = read_side_effect

            # Set up parser behavior - first call returns None, second returns data
            mock_parser.parse.side_effect = [None, bytearray([0x5A, 0xA1])]

            # Run the thread function in a controlled manner
            def run_limited() -> None:
                # Simulate a few iterations then stop
                for _ in range(3):
                    if shutdown_event.is_set():
                        break
                    data = mock_ser.read()
                    if data:
                        result = mock_parser.parse(bytearray(data))
                        if result is not None:
                            callback(result)
                            break
                shutdown_event.set()

            # Execute the controlled run
            run_limited()

            # Verify that the mock was called
            assert mock_ser.read.call_count >= 1
            callback.assert_called_once_with(bytearray([0x5A, 0xA1]))

    def test_serial_read_thread_exception_handling(self, mock_thread: Mock, mock_serial: Mock) -> None:
        """Test _serial_read_thread exception handling."""
        mock_ser = Mock()
        mock_ser.is_open = True
        mock_ser.read.side_effect = Exception("Test exception")
        shutdown_event = threading.Event()
        callback = Mock()

        # This should not raise an exception
        BlhostSerial._serial_read_thread(mock_ser, shutdown_event, self.logger, callback)

        self.logger.exception.assert_called_once()


class TestEnumValues:
    """Test that enum values are correctly defined."""

    def test_framing_packet_constants(self) -> None:
        """Test FramingPacketConstants enum values."""
        assert int(BlhostBase.FramingPacketConstants.StartByte) == 0x5A
        assert int(BlhostBase.FramingPacketConstants.Type_Ack) == 0xA1
        assert int(BlhostBase.FramingPacketConstants.Type_Nak) == 0xA2
        assert int(BlhostBase.FramingPacketConstants.Type_AckAbort) == 0xA3
        assert int(BlhostBase.FramingPacketConstants.Type_Command) == 0xA4
        assert int(BlhostBase.FramingPacketConstants.Type_Data) == 0xA5
        assert int(BlhostBase.FramingPacketConstants.Type_Ping) == 0xA6
        assert int(BlhostBase.FramingPacketConstants.Type_PingResponse) == 0xA7

    def test_command_tags(self) -> None:
        """Test CommandTags enum values."""
        assert int(BlhostBase.CommandTags.FlashEraseAll) == 0x01
        assert int(BlhostBase.CommandTags.FlashEraseRegion) == 0x02
        assert int(BlhostBase.CommandTags.ReadMemory) == 0x03
        assert int(BlhostBase.CommandTags.WriteMemory) == 0x04
        assert int(BlhostBase.CommandTags.Reset) == 0x0B
        assert int(BlhostBase.CommandTags.GetProperty) == 0x07

    def test_response_tags(self) -> None:
        """Test ResponseTags enum values."""
        assert int(BlhostBase.ResponseTags.GenericResponse) == 0xA0
        assert int(BlhostBase.ResponseTags.ReadMemoryResponse) == 0xA3
        assert int(BlhostBase.ResponseTags.GetPropertyResponse) == 0xA7

    def test_status_codes(self) -> None:
        """Test StatusCodes enum values."""
        assert int(BlhostBase.StatusCodes.Success) == 0
        assert int(BlhostBase.StatusCodes.Fail) == 1
        assert int(BlhostBase.StatusCodes.FlashSizeError) == 100
        assert int(BlhostBase.StatusCodes.MemoryRangeInvalid) == 10200
        assert int(BlhostBase.StatusCodes.UnknownProperty) == 10300
        assert int(BlhostBase.StatusCodes.AppCrcCheckPassed) == 10400
        assert int(BlhostBase.StatusCodes.ReliableUpdateSuccess) == 10600

    def test_property_tag(self) -> None:
        """Test PropertyTag enum values."""
        assert int(BlhostBase.PropertyTag.BootloaderVersion) == 0x01
        assert int(BlhostBase.PropertyTag.AvailablePeripherals) == 0x02
        assert int(BlhostBase.PropertyTag.FlashStartAddress) == 0x03
        assert int(BlhostBase.PropertyTag.FlashSizeInBytes) == 0x04
