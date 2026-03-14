import socket
import struct
import json
import zlib
import time
import threading

HOST = '127.0.0.1'
PORT = 8888
HEADER = b'\xAA\x55'

def pack(cmd_id, payload_dict):
    payload_bytes = json.dumps(payload_dict).encode('utf-8')
    length = len(payload_bytes)
    data_to_checksum = struct.pack('!B', cmd_id) + payload_bytes
    crc = zlib.crc32(data_to_checksum)
    return (HEADER + struct.pack('!I', length) + struct.pack('!B', cmd_id) + 
            payload_bytes + struct.pack('!I', crc))

def test_commands():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((HOST, PORT))
        print("Connected to simulator")
        
        # 1. Test Toggle Real Photo
        print("Sending Toggle Real Photo (0x11)...")
        sock.send(pack(0x11, {}))
        time.sleep(1)
        
        # 2. Test Snapshot
        print("Sending Snapshot Request (0x12)...")
        sock.send(pack(0x12, {}))
        time.sleep(1)
        
        # 3. Test Recording Start
        print("Sending Recording Start (0x13)...")
        sock.send(pack(0x13, {}))
        time.sleep(2)
        
        # 4. Test Recording Stop
        print("Sending Recording Stop (0x13)...")
        sock.send(pack(0x13, {}))
        time.sleep(1)
        
        print("Tests completed successfully (Check simulator logs for confirmation)")
        sock.close()
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_commands()
