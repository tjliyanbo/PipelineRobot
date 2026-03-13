import asyncio
import json
import sys
import os
import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from simulator import Protocol

# Test Configuration
HOST = '127.0.0.1'
PORT = 8888

async def run_integration_test():
    print("Starting Integration Test...")
    try:
        reader, writer = await asyncio.open_connection(HOST, PORT)
        print("Connected to Simulator")
        
        # 1. Send Control Command
        print("Sending Control Command (Speed=0.8)...")
        cmd = {"speed": 0.8, "turn": 0.0}
        packet = Protocol.pack(0x02, cmd)
        writer.write(packet)
        await writer.drain()
        
        # 2. Wait for Telemetry and Verify State Change
        print("Waiting for Telemetry...")
        start_time = time.time()
        success = False
        
        buffer = b''
        while time.time() - start_time < 5.0: # 5s timeout
            data = await reader.read(1024)
            if not data: break
            buffer += data
            
            while True:
                result, buffer = Protocol.unpack(buffer)
                if result is None: break
                
                cmd_id, payload = result
                if cmd_id == 0x80: # Telemetry
                    print(f"Received Telemetry: {payload}")
                    if payload.get("speed") == 0.8 and payload.get("status") == "MOVING":
                        print("SUCCESS: State updated correctly!")
                        success = True
                        break
            if success: break
            
        if not success:
            print("FAILURE: State did not update or timeout.")
            
        print("Closing connection...")
        writer.close()
        await writer.wait_closed()
        
    except ConnectionRefusedError:
        print("ERROR: Could not connect. Is the simulator running?")

if __name__ == '__main__':
    asyncio.run(run_integration_test())
