import asyncio
import json
import struct
import time
import random
import zlib
import cv2
import numpy as np
import socket
from render_engine import RenderEngine

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
            "humidity": 60.0,
            "roll": 0.0,
            "status": "IDLE",
            "video_enabled": False,
            "light_enabled": True
        }
        self.clients = set()
        self.running = True
        
        # UDP Video Socket
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (HOST, UDP_VIDEO_PORT)
        
        # 3D Render Engine
        try:
            self.renderer = RenderEngine(640, 480)
            print("3D Render Engine Initialized")
        except Exception as e:
            print(f"Failed to initialize 3D Engine: {e}")
            self.renderer = None

    async def update_state(self):
        while self.running:
            if self.state["speed"] != 0:
                self.state["battery"] -= 0.05
            else:
                self.state["battery"] -= 0.01
            
            self.state["temperature"] = 25.0 + random.uniform(-0.5, 0.5)
            self.state["pressure"] = 101.3 + random.uniform(-0.1, 0.1)
            self.state["humidity"] = 60.0 + random.uniform(-2.0, 2.0)
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
                    except Exception as e:
                        print(f"Telemetry send error: {e}")
                        self.clients.discard(writer)
            await asyncio.sleep(0.2) # Reduce rate to 5Hz to prevent congestion

    async def stream_video(self):
        frame_counter = 0
        while self.running:
            if self.state["video_enabled"]:
                if self.renderer:
                    # Use 3D Engine
                    img = self.renderer.render(self.state)
                else:
                    # Fallback to simple OpenCV drawing
                    img = np.zeros((480, 640, 3), np.uint8)
                    offset = int(frame_counter * self.state["speed"] * 10) % 40
                    for i in range(0, 640, 40):
                        cv2.line(img, (i + offset, 0), (i + offset, 480), (50, 50, 50), 2)
                
                # Resize FIRST to ensure text is sharp on the final image
                # 3D frames are detailed and large, so we downscale for transmission
                # Use INTER_AREA for better downscaling quality (less aliasing)
                img_small = cv2.resize(img, (320, 240), interpolation=cv2.INTER_AREA)
                
                # Draw Overlay Info (Battery, Speed) - Post-resize for sharpness
                # Adjusted coordinates and font scale for 320x240 resolution
                # Use LINE_AA for anti-aliasing
                # Font Scale 0.5 is good for 320x240. 0.6 might be slightly large but readable.
                # Ensure thickness is 1 for clarity.
                cv2.putText(img_small, f"BAT: {self.state['battery']:.1f}%", (5, 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                cv2.putText(img_small, f"SPD: {self.state['speed']:.1f}", (5, 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
                
                # Encode as JPEG with lower quality to ensure it fits
                _, buffer = cv2.imencode('.jpg', img_small, [int(cv2.IMWRITE_JPEG_QUALITY), 70]) # Quality 70 for sharper text
                data = buffer.tobytes()
                
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
                
            await asyncio.sleep(0.033) # ~30 FPS

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
            try:
                writer.close()
            except:
                pass
                
            # Note: Video state is now independent of TCP connection
            # We do NOT auto-disable video here anymore to support "independent links"

    def process_command(self, cmd_id, payload):
        print(f"Received Cmd: {cmd_id}, Payload: {payload}")
        if cmd_id == 0x01: # Heartbeat
            pass 
        elif cmd_id == 0x02: # Control
            self.state["speed"] = payload.get("speed", 0)
            self.state["turn"] = payload.get("turn", 0)
            if "light" in payload:
                self.state["light_enabled"] = bool(payload["light"])
            
            # Handle Camera Reset (Yaw)
            if payload.get("reset_yaw", False) and self.renderer:
                self.renderer.yaw = 0.0
                print("Camera Yaw Reset")
                
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
