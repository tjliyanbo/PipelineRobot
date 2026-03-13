import asyncio
import json
import struct
import time
import random
import zlib
import cv2
import numpy as np
import socket

# Configuration
HOST = '127.0.0.1'
PORT = 8888
UDP_VIDEO_PORT = 8889
HEADER = b'\xAA\x55'

class Protocol:
    @staticmethod
    def pack(cmd_id, payload_dict):
        payload_bytes = json.dumps(payload_dict).encode('utf-8')
        length = len(payload_bytes)
        data_to_checksum = struct.pack('!B', cmd_id) + payload_bytes
        crc = zlib.crc32(data_to_checksum)
        
        packet = (
            HEADER +
            struct.pack('!I', length) +
            struct.pack('!B', cmd_id) +
            payload_bytes +
            struct.pack('!I', crc)
        )
        return packet

    @staticmethod
    def unpack(buffer):
        if len(buffer) < 11:
            return None, buffer
        
        if buffer[:2] != HEADER:
            try:
                idx = buffer.find(HEADER, 1)
                if idx != -1:
                    return None, buffer[idx:]
                else:
                    return None, b''
            except:
                return None, b''

        length = struct.unpack('!I', buffer[2:6])[0]
        if len(buffer) < 6 + 1 + length + 4:
            return None, buffer
        
        cmd_id = struct.unpack('!B', buffer[6:7])[0]
        payload_bytes = buffer[7:7+length]
        received_crc = struct.unpack('!I', buffer[7+length:7+length+4])[0]
        
        data_to_checksum = struct.pack('!B', cmd_id) + payload_bytes
        calc_crc = zlib.crc32(data_to_checksum)
        
        if calc_crc != received_crc:
            print(f"CRC Error: Calc {calc_crc} != Recv {received_crc}")
            return None, buffer[7+length+4:] 
            
        try:
            payload = json.loads(payload_bytes.decode('utf-8'))
        except:
            payload = {}
            
        return (cmd_id, payload), buffer[7+length+4:]

class RobotSimulator:
    def __init__(self):
        self.state = {
            "battery": 100.0,
            "speed": 0.0,
            "turn": 0.0,
            "pressure": 101.3,
            "temperature": 25.0,
            "pitch": 0.0,
            "roll": 0.0,
            "status": "IDLE",
            "video_enabled": False
        }
        self.clients = set()
        self.running = True
        
        # UDP Video Socket
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (HOST, UDP_VIDEO_PORT)

    async def update_state(self):
        while self.running:
            if self.state["speed"] != 0:
                self.state["battery"] -= 0.05
            else:
                self.state["battery"] -= 0.01
            
            self.state["temperature"] = 25.0 + random.uniform(-0.5, 0.5)
            self.state["pressure"] = 101.3 + random.uniform(-0.1, 0.1)
            if self.state["battery"] < 0: self.state["battery"] = 0
            
            await asyncio.sleep(0.1)

    async def send_telemetry(self):
        while self.running:
            if self.clients:
                packet = Protocol.pack(0x80, self.state)
                for writer in list(self.clients):
                    try:
                        writer.write(packet)
                        await writer.drain()
                    except:
                        self.clients.remove(writer)
            await asyncio.sleep(0.05)

    async def stream_video(self):
        frame_counter = 0
        while self.running:
            if self.state["video_enabled"] and self.clients:
                # Generate a dummy frame using OpenCV
                img = np.zeros((480, 640, 3), np.uint8)
                
                # Draw background based on speed (moving stripes effect)
                offset = int(frame_counter * self.state["speed"] * 10) % 40
                for i in range(0, 640, 40):
                    cv2.line(img, (i + offset, 0), (i + offset, 480), (50, 50, 50), 2)
                
                # Draw text info
                cv2.putText(img, f"BAT: {self.state['battery']:.1f}%", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(img, f"SPD: {self.state['speed']:.1f}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                cv2.putText(img, time.strftime("%H:%M:%S"), (500, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
                
                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                data = buffer.tobytes()
                
                # Send via UDP (Handling MTU fragmentation if needed, but for simplicity sending single packet if small enough)
                # Max UDP payload ~65KB. 640x480 JPEG at 80% is usually < 50KB.
                try:
                    if len(data) < 60000:
                        self.udp_sock.sendto(data, self.udp_addr)
                        if frame_counter % 30 == 0:
                            print(f"Sent video frame {frame_counter}, size: {len(data)} bytes")
                    else:
                        print(f"Frame too large for UDP: {len(data)} bytes")
                except Exception as e:
                    print(f"UDP Error: {e}")
                
                frame_counter += 1
                
            await asyncio.sleep(0.04) # ~25 FPS

    async def handle_client(self, reader, writer):
        addr = writer.get_extra_info('peername')
        print(f"New connection from {addr}")
        self.clients.add(writer)
        
        # Add udp_addr for this client (assuming local for now, but in real world might need handshake)
        # For simulation, we just stream to localhost:8889 regardless of who connects via TCP
        # But if we want to be strict, we could look at addr[0]
        
        buffer = b''
        try:
            while self.running:
                try:
                    data = await reader.read(1024)
                    if not data: 
                        print(f"Client {addr} disconnected (EOF)")
                        break
                    
                    # Debug: Print raw data
                    # print(f"Raw Recv: {data.hex()}")
                    
                    buffer += data
                    while True:
                        result, buffer = Protocol.unpack(buffer)
                        if result is None: break
                        cmd_id, payload = result
                        self.process_command(cmd_id, payload)
                except ConnectionResetError:
                    print(f"Client {addr} connection reset")
                    break
                    
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            print(f"Connection closed {addr}")
            self.clients.discard(writer)
            writer.close()
            # Stop video when client disconnects
            if not self.clients:
                self.state["video_enabled"] = False
                print("All clients disconnected, video disabled")

    def process_command(self, cmd_id, payload):
        print(f"Received Cmd: {cmd_id}, Payload: {payload}")
        if cmd_id == 0x01: # Heartbeat
            pass 
        elif cmd_id == 0x02: # Control
            self.state["speed"] = payload.get("speed", 0)
            self.state["turn"] = payload.get("turn", 0)
            self.state["status"] = "MOVING" if self.state["speed"] != 0 else "IDLE"
        elif cmd_id == 0x10: # Video Control
            # Fix: Ensure payload key matches what host sends ("enabled") and value is boolean
            # Host sends: { enabled: true/false }
            # Let's log payload to debug
            print(f"Video Control Payload: {payload}")
            self.state["video_enabled"] = bool(payload.get("enabled", False))
            print(f"Video State Set To: {'Enabled' if self.state['video_enabled'] else 'Disabled'}")

    async def start(self):
        server = await asyncio.start_server(self.handle_client, HOST, PORT)
        print(f'Simulator serving on {HOST}:{PORT}')
        print(f'Video streaming to UDP {HOST}:{UDP_VIDEO_PORT}')
        
        async with server:
            await asyncio.gather(
                server.serve_forever(),
                self.update_state(),
                self.send_telemetry(),
                self.stream_video()
            )

if __name__ == '__main__':
    sim = RobotSimulator()
    try:
        asyncio.run(sim.start())
    except KeyboardInterrupt:
        pass
