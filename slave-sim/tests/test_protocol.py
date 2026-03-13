import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from simulator import Protocol
import zlib
import struct
import json

class TestProtocol(unittest.TestCase):
    def test_pack_unpack(self):
        cmd_id = 0x02
        payload = {"speed": 0.5, "turn": -0.1}
        
        # Test Pack
        packet = Protocol.pack(cmd_id, payload)
        self.assertTrue(len(packet) > 11)
        self.assertEqual(packet[:2], b'\xAA\x55')
        
        # Test Unpack
        result, remainder = Protocol.unpack(packet)
        self.assertIsNotNone(result)
        recv_cmd, recv_payload = result
        self.assertEqual(recv_cmd, cmd_id)
        self.assertAlmostEqual(recv_payload["speed"], 0.5)
        self.assertEqual(remainder, b'')

    def test_crc_error(self):
        cmd_id = 0x01
        payload = {}
        packet = Protocol.pack(cmd_id, payload)
        
        # Corrupt the CRC (last 4 bytes)
        corrupted = packet[:-1] + b'\x00'
        
        result, remainder = Protocol.unpack(corrupted)
        self.assertIsNone(result)
        # Should skip the packet (return remainder after header/len check failure or full packet skip)
        # In my implementation, if CRC fails, it returns None and skips the whole packet payload+crc
        # It returns buffer[7+length+4:] which is empty here
        self.assertEqual(remainder, b'')

if __name__ == '__main__':
    unittest.main()
