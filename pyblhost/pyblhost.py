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

import argparse
import logging
import struct
import threading
from enum import IntEnum
from typing import Callable, Optional, Generator, Union, Type

import can
import serial
from tqdm import tqdm

from pyblhost import __version__


class BlhostBase(object):
    """
    Implemented based on "Kinetis Bootloader v2.0.0 Reference Manual.pdf" and
    existing blhost application: https://github.com/Lauszus/blhost
    """

    class FramingPacketConstants(IntEnum):
        StartByte = 0x5a
        Type_Ack = 0xa1
        Type_Nak = 0xa2
        Type_AckAbort = 0xa3
        Type_Command = 0xa4
        Type_Data = 0xa5
        Type_Ping = 0xa6
        Type_PingResponse = 0xa7

    class CommandTags(IntEnum):
        FlashEraseAll = 0x01
        FlashEraseRegion = 0x02
        ReadMemory = 0x03
        WriteMemory = 0x04
        FillMemory = 0x05
        FlashSecurityDisable = 0x06
        GetProperty = 0x07
        ReceiveSbFile = 0x08
        Execute = 0x09
        Call = 0x0a
        Reset = 0x0b
        SetProperty = 0x0c
        FlashEraseAllUnsecure = 0x0d
        FlashProgramOnce = 0x0e
        FlashReadOnce = 0x0f
        FlashReadResource = 0x10
        FlashReadResourceResponse = 0xb0
        ConfigureQuadSpi = 0x11
        ReliableUpdate = 0x12

    class ResponseTags(IntEnum):
        GenericResponse = 0xa0
        ReadMemoryResponse = 0xa3
        GetPropertyResponse = 0xa7
        FlashReadOnceResponse = 0xaf

    class PropertyTag(IntEnum):
        BootloaderVersion = 0x01
        AvailablePeripherals = 0x02
        FlashStartAddress = 0x03
        FlashSizeInBytes = 0x04
        FlashSectorSize = 0x05
        FlashBlockCount = 0x06
        AvailableCommands = 0x07
        CrcCheckStatus = 0x08
        # Reserved9 = 0x09
        VerifyWrites = 0x0a
        MaxPacketSize = 0x0b
        ReservedRegions = 0x0c
        # Reserved13 = 0x0d
        RAMStartAddress = 0x0e
        RAMSizeInBytes = 0x0f
        SystemDeviceId = 0x10
        FlashSecurityState = 0x11
        UniqueDeviceId = 0x12
        FacSupport = 0x13
        FlashAccessSegmentSize = 0x14
        FlashAccessSegmentCount = 0x15
        FlashReadMargin = 0x16
        QspiInitStatus = 0x17
        TargetVersion = 0x18
        ExternalMemoryAttributes = 0x19
        ReliableUpdateStatus = 0x1a

    class StatusCodes(IntEnum):
        # Generic statuses
        Success = 0
        Fail = 1
        ReadOnly = 2
        OutOfRange = 3
        InvalidArgument = 4
        Timeout = 5
        NoTransferInProgress = 6

        # Flash driver errors
        FlashSizeError = 100
        FlashAlignmentError = 101
        FlashAddressError = 102
        FlashAccessError = 103
        FlashProtectionViolation = 104
        FlashCommandFailure = 105
        FlashUnknownProperty = 106
        FlashEraseKeyError = 107
        FlashRegionExecuteOnly = 108
        FlashExecuteInRamFunctionNotReady = 109

        # Memory interface errors
        MemoryRangeInvalid = 10200
        MemoryReadFailed = 10201
        MemoryWriteFailed = 10202
        MemoryCumulativeWrite = 10203
        MemoryAppOverlapWithExecuteOnlyRegion = 10204

        # Property store errors
        UnknownProperty = 10300
        ReadOnlyProperty = 10301
        InvalidPropertyValue = 10302

        # Application crc check statuses
        AppCrcCheckPassed = 10400
        AppCrcCheckFailed = 10401
        AppCrcCheckInactive = 10402
        AppCrcCheckInvalid = 10403
        AppCrcCheckOutOfRange = 10404

        # Reliable Update statuses
        ReliableUpdateSuccess = 10600  # Reliable Update succeeded
        ReliableUpdateFail = 10601  # Reliable Update failed
        ReliableUpdateInactive = 10602  # Reliable Update Feature is inactive
        ReliableUpdateBackupApplicationInvalid = 10603  # Backup Application is invalid
        ReliableUpdateStillInMainApplication = 10604  # Next boot will be still in Main Application
        ReliableUpdateSwapSystemNotReady = 10605  # Cannot swap flash by default because swap system is not ready
        ReliableUpdateBackupBootloaderNotReady = 10606  # Cannot swap flash because there is no valid backup bootloader
        ReliableUpdateSwapIndicatorAddressInvalid = 10607  # Cannot swap flash because provided swap indicator is invalid

    def __init__(self, logger):
        self.logger = logger

        # Make sure sending data is always atomic
        self._send_lock = threading.Lock()

        # Used to re-send the previous packet if NAK is received
        self._last_send_packet = None

        # Flags used when uploading
        self._ack_response_event = threading.Event()
        self._reset_response_event = threading.Event()
        self._flash_erase_region_response_event = threading.Event()
        self._read_memory_response_tag_event = threading.Event()
        self._write_memory_response_event = threading.Event()
        self._read_memory_response_event = threading.Event()
        self._data_event = threading.Event()
        self._ping_response_event = threading.Event()

        # Used to store memory data when reading
        self._memory_data = bytearray()

    def _send_implementation(self, data: list):
        raise NotImplementedError

    def _send(self, data: list):
        with self._send_lock:
            self._last_send_packet = data
            self._send_implementation(data)

    def shutdown(self, timeout=1.0):
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.shutdown()

    def ping(self, timeout=5.0) -> bool:
        self.logger.info('BlhostBase: Sending ping command')
        self._ping_response_event.clear()
        data = [self.FramingPacketConstants.StartByte, self.FramingPacketConstants.Type_Ping]
        self._send(data)
        return self._ping_response_event.wait(timeout)

    def reset(self, timeout=5.0) -> bool:
        self.logger.info('BlhostBase: Sending reset command')
        self._reset_response_event.clear()
        self._command_packet(self.CommandTags.Reset, 0x00)
        return self._reset_response_event.wait(timeout)

    def upload(self, binary_filename: str, start_address: int, erase_byte_count: int, timeout=5.0, ping_repeat=3) -> Generator[Union[float, bool], None, None]:
        self.logger.info('BlhostBase: Uploading "{}" to 0x{:X}'.format(binary_filename, start_address))

        # Read the binary data from the file
        with open(binary_filename, 'rb') as f:
            binary_data = f.read()

        # "The byte count is rounded up to a multiple of 4, and trailing bytes are filled with the
        # flash erase pattern (0xff)."
        # However this is wrong! For the MK66FX1M0xxx18 it needs to be 16-byte aligned
        if len(binary_data) % 16 != 0:
            binary_data += bytes([0xff] * (16 - (len(binary_data) % 16)))

        try:
            # Yield a progress while uploading and store the return value
            upload_result = yield from self._upload(binary_data, start_address, erase_byte_count, timeout, ping_repeat)

            # We need to clear the backup region if uploading fails.
            if not upload_result:
                self.logger.info('BlhostBase: Uploading failed. Erasing flash region: 0x{:X} -> 0x{:X}'.format(
                    start_address, start_address + erase_byte_count))
                self._flash_erase_region_response_event.clear()
                self._flash_erase_region(start_address, erase_byte_count)
                if not self._flash_erase_region_response_event.wait(timeout):
                    self.logger.error('BlhostBase: Timed out waiting for flash erase region response after the upload failed')
        finally:
            # Make sure the target is always reset
            if not self.reset(timeout=timeout):
                # This is BAD. This could make the flight controller stay in bootloader mode!
                self.logger.error('BlhostBase: Timed out waiting for reset response')
                upload_result = False

        # Finally yield the result
        yield upload_result

    def _upload(self, binary_data: bytes, start_address: int, erase_byte_count: int, timeout: float, ping_repeat: int) -> Generator[float, None, bool]:
        # Try to ping the target 3 times to make sure we can communicate with the bootloader
        for i in range(ping_repeat):
            if self.ping(timeout=timeout):
                self.logger.info('BlhostBase: Ping responded in {} attempt(s)'.format(i + 1))
                break
        else:
            self.logger.warning('BlhostBase: Target did not respond to ping')
            return False

        # First erase the region of memory where application will be located
        # The application will be flashed when this command succeeds
        self.logger.info('BlhostBase: Erasing flash region: 0x{:X} -> 0x{:X}'.format(
            start_address, start_address + erase_byte_count))
        self._flash_erase_region_response_event.clear()
        self._flash_erase_region(start_address, erase_byte_count)
        if not self._flash_erase_region_response_event.wait(timeout):
            self.logger.warning('BlhostBase: Timed out waiting for initial flash erase region response')
            return False

        self.logger.info('BlhostBase: Sending write memory command')
        self._write_memory_response_event.clear()
        self._write_memory(start_address, binary_data)
        if not self._write_memory_response_event.wait(timeout):
            self.logger.warning('BlhostBase: Timed out waiting for write memory response')
            return False

        # This flag will be set when uploading has finished
        self._write_memory_response_event.clear()

        # We need to send the data in chunks of 32 bytes
        # When an ACK is received we can send the next chunk
        yield 0  # The progress starts at 0 %
        data_sent = 0
        for d in self.chunks(binary_data, 32):
            self._ack_response_event.clear()
            self._data_packet(*d)
            if not self._ack_response_event.wait(timeout):
                self.logger.warning('BlhostBase: Timed out waiting for ACK response')
                return False

            # Yield the progress in percent
            data_sent += len(d)
            yield data_sent / len(binary_data) * 100.

        if self._write_memory_response_event.wait(timeout):
            # "The target returns a GenericResponse packet with a status code set to
            # kStatus_Success upon successful execution of the command, or to an appropriate error
            # status code."
            return True

        return False

    def _ack(self):
        data = [self.FramingPacketConstants.StartByte, self.FramingPacketConstants.Type_Ack]
        self._send(data)

    @staticmethod
    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    @staticmethod
    def crc16Xmodem(data: Union[bytes, list], crc_init: int = 0) -> int:
        """
        Calculate XMODEM 16-bit CRC from input data
        :param data: Input data
        :param crc_init: Initialization value
        """
        crc = crc_init
        for c in data:
            crc ^= c << 8
            for _ in range(8):
                temp = crc << 1
                if crc & 0x8000:
                    temp ^= 0x1021
                crc = temp
        return crc & 0xFFFF

    def _framing_packet(self, packet_type: FramingPacketConstants, length: int, *payload):
        # The CRC16 value is calculated on all the data
        crc16 = self.crc16Xmodem([self.FramingPacketConstants.StartByte, packet_type, length & 0xFF,
                                  (length >> 8) & 0xFF, *payload])

        # Construct the frame header
        data = [
            self.FramingPacketConstants.StartByte,
            packet_type,
            length & 0xFF,
            (length >> 8) & 0xFF,
            crc16 & 0xFF,
            (crc16 >> 8) & 0xFF,
        ]

        # Append the payload
        data.extend(payload)

        # Send the data to the target
        self._send(data)

    def _command_packet(self, tag: CommandTags, flags: int, *payload):
        """Used for sending commands to the target"""
        self._framing_packet(self.FramingPacketConstants.Type_Command, 4 + len(payload), tag, flags, 0, len(payload),
                             *payload)

    def _data_packet(self, *payload):
        """Used for sending data to the target"""
        self._framing_packet(self.FramingPacketConstants.Type_Data, len(payload), *payload)

    def _get_property(self, property_tag: PropertyTag, memory_id=0):
        # Memory ID: 0 = Internal flash, 0x01 = QSPI0 memory
        self._command_packet(self.CommandTags.GetProperty, 0x00,
                             *[x for x in struct.Struct('<LL').pack(property_tag, memory_id)])

    def _flash_erase_region(self, start_address: int, byte_count: int):
        self._command_packet(self.CommandTags.FlashEraseRegion, 0x00,
                             *[x for x in struct.Struct('<LL').pack(start_address, byte_count)])

    def read(self, start_address: int, byte_count: int, timeout=5.0, ping_repeat=3) -> \
            Generator[Union[float, bytearray], None, None]:
        # Try to ping the target 3 times to make sure we can communicate with the bootloader
        for i in range(ping_repeat):
            if self.ping(timeout=timeout):
                self.logger.info('BlhostBase: Ping responded in {} attempt(s)'.format(i + 1))
                break
        else:
            self.logger.warning('BlhostBase: Target did not respond to ping')
            return

        # Clear any data that was read before
        self._memory_data.clear()

        # Make sure the flags are cleared
        self._data_event.clear()
        self._read_memory_response_tag_event.clear()

        # Send the read memory command
        self._read_memory_response_event.clear()
        self._read_memory(start_address, byte_count)
        if not self._read_memory_response_event.wait(timeout):
            self.logger.error('BlhostBase: Timed out waiting for read memory response')
            return

        while True:
            yield len(self._memory_data) / byte_count * 100.
            if not self._data_event.wait(timeout):
                if self._read_memory_response_tag_event.is_set():
                    # We are done reading all the data
                    yield 100.
                    break
                self.logger.error('BlhostBase: Timed out waiting for read memory data event')
                return
            self._data_event.clear()

        if len(self._memory_data) != byte_count:
            self.logger.error('BlhostBase: Memory data does not have the correct length: {} != {}'.format(
                len(self._memory_data), byte_count))
            return

        yield self._memory_data

    def _read_memory(self, start_address: int, byte_count: int):
        self._command_packet(self.CommandTags.ReadMemory, 0x00,
                             *[x for x in struct.Struct('<LL').pack(start_address, byte_count)])

    def _write_memory(self, start_address: int, data: bytes):
        self._command_packet(self.CommandTags.WriteMemory, 0x00,
                             *[x for x in struct.Struct('<LL').pack(start_address, len(data))])

    def _reliable_update(self, address=0):
        """
        Can be used to make the target perform "reliable update operation".
        Note it will also do this during reset
        """
        self._command_packet(self.CommandTags.ReliableUpdate, 0x00, *[x for x in struct.Struct('<L').pack(address)])

    # This will be called by the listener i.e. in a different thread!
    def _data_callback(self, data: bytearray) -> None:
        if data[0] != self.FramingPacketConstants.StartByte:
            self.logger.error('BlhostBase: Invalid start byte: {}'.format(data))
            return

        # We never parse the CRC16, as that has already been done when parsing the data
        if data[1] == self.FramingPacketConstants.Type_Ack:
            # The previous packet was received successfully; the sending of more packets is allowed
            self.logger.debug('BlhostBase: Received ACK')
            self._ack_response_event.set()
        elif data[1] == self.FramingPacketConstants.Type_Nak:
            # The previous packet was corrupted and must be re-sent
            self.logger.warning('BlhostBase: Received NAK')
            if self._last_send_packet is not None:
                self.logger.info('BlhostBase: Resending last packet')
                self._send(self._last_send_packet)
        elif data[1] == self.FramingPacketConstants.Type_AckAbort:
            # Data phase is being aborted
            self.logger.error('BlhostBase: Received ACK abort')
        elif data[1] == self.FramingPacketConstants.Type_Command:
            # Acknowledge that we received the response
            self._ack()

            # length, crc16 = struct.Struct('<HH').unpack(data[2:6])
            tag, flags, _, parameter_count = struct.Struct('<BBBB').unpack(data[6:10])  # Parse the header

            # Parse the status code and convert the status code into a user friendly name if possible
            status_code = struct.Struct('<L').unpack(data[10:14])[0]
            try:
                status_name = self.StatusCodes(status_code).name
            except ValueError:
                status_name = str(status_code)

            # Set the log level based on the status code
            level = logging.INFO if status_code == self.StatusCodes.Success else logging.WARNING

            if tag == self.ResponseTags.GenericResponse:
                command_tag = struct.Struct('<L').unpack(data[14:])[0]

                # Check which command tag the response was for
                if command_tag == self.CommandTags.Reset:
                    self.logger.log(level, 'BlhostBase: CommandTag.Reset status: {}'.format(status_name))
                    if status_code == self.StatusCodes.Success:
                        self._reset_response_event.set()
                elif command_tag == self.CommandTags.FlashEraseRegion:
                    self.logger.log(level, 'BlhostBase: CommandTag.FlashEraseRegion status: {}'.format(status_name))
                    if status_code == self.StatusCodes.Success:
                        self._flash_erase_region_response_event.set()
                elif command_tag == self.CommandTags.ReadMemory:
                    self.logger.log(level, 'BlhostBase: CommandTag.ReadMemory status: {}'.format(status_name))
                    if status_code == self.StatusCodes.Success:
                        self._read_memory_response_tag_event.set()
                elif command_tag == self.CommandTags.WriteMemory:
                    self.logger.log(level, 'BlhostBase: CommandTag.WriteMemory status: {}'.format(status_name))
                    if status_code == self.StatusCodes.Success:
                        self._write_memory_response_event.set()
                elif command_tag == self.CommandTags.ReliableUpdate:
                    if status_code == self.StatusCodes.ReliableUpdateSuccess:
                        level = logging.INFO  # Change the logging level, as this is also a successfully message
                    self.logger.log(level, 'BlhostBase: CommandTag.ReliableUpdate status: {}'.format(status_name))
                else:
                    self.logger.log(level, 'BlhostBase: ResponseTags.GenericResponse: status: {}, command tag: {:02X}'
                                    .format(status_name, command_tag))
            elif tag == self.ResponseTags.ReadMemoryResponse:
                data_byte_count = struct.Struct('<L'.format()).unpack(data[14:])[0]
                self.logger.log(level, 'BlhostBase: ResponseTags.ReadMemoryResponse: status: {}, data byte count: {}'
                                .format(status_name, data_byte_count))
                if status_code == self.StatusCodes.Success:
                    self._read_memory_response_event.set()
            elif tag == self.ResponseTags.GetPropertyResponse:
                # Make sure the response actually contain any property values
                if parameter_count == 1:
                    self.logger.log(level, 'BlhostBase: ResponseTags.GetPropertyResponse: status: {}'.format(status_name))
                else:
                    # Unpack the property values and log them
                    property_values = struct.Struct('<{}L'.format(parameter_count - 1)).unpack(data[14:])
                    if len(property_values) == 1:
                        if self.StatusCodes.AppCrcCheckPassed <= property_values[0] <= \
                                self.StatusCodes.AppCrcCheckOutOfRange or \
                                self.StatusCodes.ReliableUpdateSuccess <= property_values[0] <= \
                                self.StatusCodes.ReliableUpdateSwapIndicatorAddressInvalid:
                            try:
                                property_values = self.StatusCodes(property_values[0]).name  # type: ignore
                            except ValueError:
                                property_values = property_values[0]
                    self.logger.log(level, 'BlhostBase: ResponseTags.GetPropertyResponse: status: {}, property value: {}'
                                    .format(status_name, property_values))
            # elif tag == self.ResponseTags.FlashReadOnceResponse:
            #     pass
            else:
                self.logger.error('BlhostBase: Unhandled command tag: {}'.format(tag))
        elif data[1] == self.FramingPacketConstants.Type_Data:
            # Acknowledge that we received the response
            self._ack()

            # Store the incoming data. There is no reason to check the CRC, as it has already been checked in the parser
            length = struct.Struct('<H').unpack(data[2:4])[0]
            self._memory_data += bytes(struct.Struct('<{}B'.format(length)).unpack(data[6:]))

            # Indicate that we have read the data
            self._data_event.set()
        elif data[1] == self.FramingPacketConstants.Type_PingResponse:
            self._ping_response_event.set()

            protocol_bugfix, protocol_minor, protocol_major, protocol_name, options = struct.Struct('<BBBBH').unpack(data[2:8])
            protocol_version = '{}{}.{}.{}'.format(chr(protocol_name), protocol_major, protocol_minor, protocol_bugfix)
            self.logger.info('BlhostBase: Ping response: version: {}, options: {}'.format(protocol_version, options))
            if protocol_version != 'P1.2.0':
                self.logger.error('BlhostBase: Unsupported protocol version: {}'.format(protocol_version))
        else:
            self.logger.info('BlhostBase: Unhandled command type: {}'.format(data[1]))


class BlhostDataParser(object):

    def __init__(self, logger):
        self._logger = logger
        self._data = bytearray()
        self._data_len = None  # type: Optional[int]
        self._data_crc = None  # type: Optional[int]

    def __call__(self, data) -> Optional[bytearray]:
        return self.parse(data)

    def parse(self, data: bytearray) -> Optional[bytearray]:
        """Parse the data sent from the target.
        :param data: Data received from the target.
        :return: Returns the parsed data when the messages has been parsed.
        """
        # Append the incoming data to the buffer
        self._data += data

        # The packet type will always start with the start byte
        while len(self._data) > 0 and self._data[0] != BlhostBase.FramingPacketConstants.StartByte:
            self._data = self._data[1:]  # Discard the fist byte

        if len(self._data) < 2:
            # We need more data before we can determine the type and what to do with it
            return None

        if self._data[1] in [BlhostBase.FramingPacketConstants.Type_Ack,
                             BlhostBase.FramingPacketConstants.Type_Nak,
                             BlhostBase.FramingPacketConstants.Type_AckAbort]:
            # Only return the first two bytes, as the next must be part of the next message
            message, self._data = self._data[:2], self._data[2:]
            return message
        elif self._data[1] == BlhostBase.FramingPacketConstants.Type_Ping:
            # Do not reply to ping commands, as only the host should be sending them,
            # so someone else must be trying to talk to the target
            self._logger.warning('BootloaderDataParser: Received ping command')
            self._data = self._data[2:]  # Discard the fist two bytes
            return None
        elif self._data[1] == BlhostBase.FramingPacketConstants.Type_PingResponse:
            # The length is constant for the ping response
            self._data_len = 10

            # The CRC is stored in the last bytes
            if len(self._data) >= 10 and self._data_crc is None:
                self._data_crc = self._data[8] | self._data[9] << 8
        elif self._data[1] in [BlhostBase.FramingPacketConstants.Type_Command,
                               BlhostBase.FramingPacketConstants.Type_Data]:
            if len(self._data) >= 4 and self._data_len is None:
                # Store the total length of the data i.e. start byte (uint8_t), packet type (uint8_t),
                # length (uint16_t), crc16 (uint16_t) and payload
                self._data_len = 6 + (self._data[2] | self._data[3] << 8)

            if len(self._data) >= 6 and self._data_crc is None:
                self._data_crc = self._data[4] | self._data[5] << 8
        else:
            self._logger.error('BootloaderDataParser: Unknown command type: {}'.format(self._data[1]))
            self._data = self._data[2:]  # Discard the fist two bytes
            return None

        # Check if we are done reading the packet
        if self._data_len is not None and len(self._data) == self._data_len and self._data_crc is not None:
            if self._data[1] == BlhostBase.FramingPacketConstants.Type_PingResponse:
                crc = BlhostBase.crc16Xmodem(self._data[:8])
            else:
                crc = BlhostBase.crc16Xmodem(self._data[:4])
                crc = BlhostBase.crc16Xmodem(self._data[6:self._data_len], crc)
            match = crc == self._data_crc
            if not match:
                self._logger.error('BootloaderDataParser: CRC did not match: {:04X} != {:04X}'.format(crc, self._data_crc))

            # Return the parsed message if the CRC matched; if not it will be discarded
            message, self._data = self._data[:self._data_len], self._data[self._data_len:]
            self._data_len = None
            self._data_crc = None
            if match:
                return message
        return None


class BlhostCanListener(can.Listener):

    def __init__(self, tx_id, logger, callback_func: Callable[[bytearray], None]):
        self._tx_id = tx_id
        self._logger = logger
        self._callback_func = callback_func
        self._parser = BlhostDataParser(self._logger)

    def on_message_received(self, msg: can.Message):
        # We are only interested in frames from the target
        if msg.is_error_frame or msg.is_remote_frame or msg.is_extended_id or msg.arbitration_id != self._tx_id:
            return

        # Parse the data and return it once it is fully parsed
        data = self._parser(msg.data)
        if data is not None:
            self._callback_func(data)

    def on_error(self, exc):
        self._logger.exception('BlhostCanListener: on_error')

    def stop(self):
        pass


class BlhostCan(BlhostBase):

    def __init__(self, tx_id, rx_id, logger, interface='socketcan', channel='can0', bitrate=500000):
        super(BlhostCan, self).__init__(logger)

        # CAN-Bus IDs used for two-way communication with the target
        self._tx_id = tx_id
        self._rx_id = rx_id

        # Only receive the TX ID
        can_filters = [{'can_id': self._tx_id, 'can_mask': 0x7FF, 'extended': False}]

        # Open a CAN-Bus interface and listener
        self._can_bus = can.Bus(interface=interface, channel=channel, can_filters=can_filters, bitrate=bitrate)
        self.logger.info('BlhostCan: CAN-Bus was opened. Channel info: "{}"'.format(self._can_bus.channel_info))
        self._can_notifier = can.Notifier(self._can_bus, [BlhostCanListener(self._tx_id, self.logger,
                                                                            self._data_callback)])

    def _send_implementation(self, data: list):
        # Send out the message in chunks of 8 bytes on the CAN-Bus
        for d in BlhostBase.chunks(data, 8):
            msg = can.Message(arbitration_id=self._rx_id, data=d, is_extended_id=False)
            self._can_bus.send(msg)

    def shutdown(self, timeout=1.0):
        self._can_notifier.stop(timeout=timeout)
        self._can_bus.shutdown()


class BlhostSerial(BlhostBase):

    def __init__(self, port, baudrate, logger):
        super(BlhostSerial, self).__init__(logger)

        # Open the serial port, but read from it in a thread, so we are not blocking the main loop
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=.5)
        self._shutdown_thread = threading.Event()
        self._thread = threading.Thread(target=self._serial_read_thread, name='_serial_read_thread',
                                        args=(self._serial, self._shutdown_thread, self.logger, self._data_callback))
        self._thread.daemon = False  # Make sure the application joins this before closing down
        self._thread.start()

    def _send_implementation(self, data: list):
        self._serial.write(data)

    def shutdown(self, timeout=1.0):
        self._shutdown_thread.set()
        self._thread.join(timeout=timeout)
        self._serial.close()

    @staticmethod
    def _serial_read_thread(ser: serial.Serial, shutdown_event: threading.Event, logger,
                            callback_func: Callable[[bytearray], None]):
        try:
            parser = BlhostDataParser(logger)
            while not shutdown_event.is_set() and ser.is_open:
                data = ser.read()
                if data:
                    data = parser(bytearray(data))
                    if data is not None:
                        callback_func(data)
        except Exception:
            logger.exception('BlhostSerial: Caught exception in "_serial_read_thread"')


def cli():
    parser = argparse.ArgumentParser(add_help=False, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('hw_interface', help='Communicate with the target via either CAN or serial',
                        choices=['can', 'serial'])
    parser.add_argument('command', help='upload: write BINARY to START_ADDRESS. Before writing it will erase the '
                                        'memory from START_ADDRESS to START_ADDRESS + BYTE_COUNT\n'
                                        'read: read memory from START_ADDRESS to START_ADDRESS + BYTE_COUNT. '
                                        'the read data will be stored in BINARY\n'
                                        'ping: send a ping command to the target and check for a response\n'
                                        'reset: send a reset command to the target and check for a response',
                        choices=['upload', 'read', 'ping', 'reset'])

    # Options for "can"
    required_can = parser.add_argument_group('required CAN arguments')
    required_can.add_argument('-tx', '--tx-id', help='The TX ID (in hex) to use for CAN')
    required_can.add_argument('-rx', '--rx-id', help='The RX ID (in hex) to use for CAN')

    optional_can = parser.add_argument_group('optional CAN arguments')
    optional_can.add_argument('-i', '--interface', help='The CAN-Bus interface to use (default "socketcan")',
                              default='socketcan')
    optional_can.add_argument('-l', '--channel', help='The CAN-Bus channel to use (default "can0")', default='can0')

    # Options for "serial"
    required_serial = parser.add_argument_group('required serial arguments')
    required_serial.add_argument('-p', '--port', help='The port to use for serial')

    # Common optional arguments
    optional = parser.add_argument_group('optional arguments')
    optional.add_argument('-h', '--help', action='help', help='Show this help message and exit')
    optional.add_argument('--version', action='version', help='Show program\'s version number and exit',
                          version='%(prog)s {}'.format(__version__))
    optional.add_argument('-B', '--binary', help='The binary to upload or write memory into')
    optional.add_argument('-s', '--start-address',
                          help='The address (in hex) to upload the binary at or read memory from')
    optional.add_argument('-c', '--byte-count', dest='byte_count', help='The number of bytes (in hex) to erase/read')
    optional.add_argument('-t', '--timeout', help='The time to wait in seconds for a response (default 1.0)',
                          default=1.0, type=float)
    optional.add_argument('-r', '--cmd-repeat', help='The number of times to try to establish a connection (default 3)',
                          default=3, type=int)
    optional.add_argument('-b', '--baudrate', '--bitrate',
                          help='The baudrate/bitrate to use for serial/can (default 500000)', type=int, default=500000)

    parsed_args = parser.parse_args()
    if parsed_args.hw_interface == 'can':
        if parsed_args.tx_id is None or parsed_args.rx_id is None:
            parser.print_help()
            exit(1)
        BlHostImpl = BlhostCan  # type: Type[BlhostBase]
        args, kwargs = [int(parsed_args.tx_id, base=16), int(parsed_args.rx_id, base=16)], \
            {'interface': parsed_args.interface, 'channel': parsed_args.channel, 'bitrate': parsed_args.baudrate}
    else:
        if parsed_args.port is None or parsed_args.baudrate is None:
            parser.print_help()
            exit(1)
        BlHostImpl = BlhostSerial
        args, kwargs = [parsed_args.port, parsed_args.baudrate], {}

    # Print all log output directly in the terminal
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
    logger.addHandler(stream_handler)
    kwargs['logger'] = logger

    with BlHostImpl(*args, **kwargs) as blhost:
        if parsed_args.command == 'upload':
            if parsed_args.binary is None or parsed_args.start_address is None or parsed_args.byte_count is None:
                parser.print_help()
                exit(1)
            pbar = None
            result = False
            for progress in blhost.upload(parsed_args.binary, int(parsed_args.start_address, base=16),
                                          int(parsed_args.byte_count, base=16), timeout=parsed_args.timeout,
                                          ping_repeat=parsed_args.cmd_repeat):
                if not isinstance(progress, bool):
                    if pbar is None:
                        # Create it here, so the progress is not printed before we actually start uploading
                        pbar = tqdm(desc='[INFO] Upload progress', total=100, bar_format='{l_bar}{bar}| [{elapsed}]',
                                    dynamic_ncols=True)
                    pbar.update(progress - pbar.n)
                    if progress >= 100:
                        # Ensure nothing is printed after the update finishes
                        pbar.close()
                else:
                    result = progress
            if pbar is not None:
                pbar.close()  # Make sure it is closed
            if result is True:
                blhost.logger.info('Uploading succeeded')
                exit(0)
            else:
                blhost.logger.error('Uploading failed')
                exit(1)
        elif parsed_args.command == 'read':
            if parsed_args.binary is None or parsed_args.start_address is None or parsed_args.byte_count is None:
                parser.print_help()
                exit(1)
            pbar = None
            data = None
            for progress in blhost.read(int(parsed_args.start_address, base=16),
                                        int(parsed_args.byte_count, base=16), timeout=parsed_args.timeout,
                                        ping_repeat=parsed_args.cmd_repeat):
                if not isinstance(progress, bytearray):
                    if pbar is None:
                        # Create it here, so the progress is not printed before we actually start uploading
                        pbar = tqdm(desc='[INFO] Read memory', total=100, bar_format='{l_bar}{bar}| [{elapsed}]',
                                    dynamic_ncols=True)
                    pbar.update(progress - pbar.n)
                    if progress >= 100:
                        # Ensure nothing is printed after the update finishes
                        pbar.close()
                else:
                    data = progress
            if pbar is not None:
                pbar.close()  # Make sure it is closed
            if data is None:
                blhost.logger.error('Reading memory failed')
                exit(1)
            with open(parsed_args.binary, 'wb') as f:
                f.write(data)
            blhost.logger.info('Reading memory succeeded')
            exit(0)
        elif parsed_args.command == 'ping':
            for i in range(parsed_args.cmd_repeat):
                if blhost.ping(timeout=parsed_args.timeout):
                    blhost.logger.info('Ping responded in {} attempt(s)'.format(i + 1))
                    exit(0)

            blhost.logger.error('Timed out waiting for ping response')
            exit(1)
        else:
            for i in range(parsed_args.cmd_repeat):
                if blhost.reset(timeout=parsed_args.timeout):
                    blhost.logger.info('Reset responded in {} attempt(s)'.format(i + 1))
                    exit(0)

            blhost.logger.error('Timed out waiting for reset response')
            exit(1)


if __name__ == '__main__':
    cli()
