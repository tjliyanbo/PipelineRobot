import asyncio
import json
import struct
import time
import random
import zlib
import cv2
import numpy as np
import socket
import os
from datetime import datetime
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
        
        # Recording State
        self.recording = False
        self.video_writer = None
        self.snapshot_request = False
        self.record_start_time = 0
        
        # Ensure outputs directory exists
        os.makedirs("outputs", exist_ok=True)
        
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
                
                # --- Recording and Snapshot Logic (High Quality) ---
                current_time = datetime.now()
                
                if self.snapshot_request:
                    filename = f"outputs/snapshot_{current_time.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                    cv2.imwrite(filename, img)
                    print(f"Snapshot saved: {filename}")
                    self.snapshot_request = False
                    
                if self.recording:
                    if self.video_writer is None:
                        filename = f"outputs/record_{current_time.strftime('%Y%m%d_%H%M%S')}.mp4"
                        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                        self.video_writer = cv2.VideoWriter(filename, fourcc, 30.0, (640, 480))
                        print(f"Recording started: {filename}")
                        
                    # Add timestamp to recording
                    rec_img = img.copy()
                    cv2.putText(rec_img, current_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 470), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    self.video_writer.write(rec_img)
                elif self.video_writer is not None:
                    self.video_writer.release()
                    self.video_writer = None
                    print("Recording stopped")

                # Resize FIRST to ensure text is sharp on the final image
                # 3D frames are detailed and large, so we downscale for transmission
                # Use INTER_AREA for better downscaling quality (less aliasing)
                
                # Check aspect ratio of original image
                h, w = img.shape[:2]
                
                # If we are in real photo mode, we want to preserve aspect ratio if possible
                # But UDP limit is strict. 320x240 is 4:3. 
                # If source is 1024x1024 (1:1), 320x240 will squash it.
                # However, the RenderEngine.render() method ALREADY returns a 640x480 image (4:3)
                # because the OpenGL viewport is set to 640x480.
                # Even if the texture is 1024x1024, it's mapped onto a cylinder and rendered to 640x480.
                # So the "squashing" happens during 3D projection if the UV mapping isn't adjusted,
                # OR it happens here if we force resize.
                
                # Wait, render_engine.py sets viewport to (width, height) which is 640, 480.
                # So `img` is 640x480.
                # If the texture is 1:1, and mapped to a pipe, it depends on UVs.
                # BUT, if the user means the "Photo Mode" which might just be displaying the raw texture?
                # No, RenderEngine.render() draws the pipe with the texture.
                # If the user wants to see the photo "as is", they might be expecting a 2D blit of the photo,
                # not a 3D pipe rendering.
                # But my code in render_engine.py does "draw_pipe". 
                # It wraps the 1024x1024 photo around the cylinder.
                
                # However, if the user implies the "Real Photo Mode" logic I implemented in render_engine.py
                # involved warpPolar... 
                # Let's look at render_engine.py again.
                # It loads the photo, warps it to rectangular (if enabled), and uses it as a texture.
                # Then `render()` renders the 3D scene.
                # The output of `render()` is ALWAYS 640x480 (from __init__).
                
                # If the user wants to see the 1:1 aspect ratio, we have a mismatch.
                # The simulator output is defined as 640x480 (4:3).
                # If we want 1:1, we'd need to change the render resolution or add black bars (letterboxing).
                
                # BUT, the UDP transport resizes to 320x240 (4:3).
                # So 1:1 input -> 4:3 render -> 4:3 UDP -> 4:3 Display.
                # The distortion happens because 1024x1024 texture is stretched to cover the pipe surface?
                # Or simply because the user expects the square photo to appear square in the video feed?
                
                # If I want to support 1:1 display in the host app, I need to send a 1:1 stream.
                # E.g. 240x240.
                # But the host app video element is flexible.
                
                # Let's try to fit the image into 320x240 while preserving aspect ratio using black bars (Letterboxing).
                # Only if the source implies a different aspect? 
                # Currently `img` comes from `render()` which is 640x480.
                
                # If the User says "I provided a 1024x1024 photo", they might be referring to the "Real Photo Mode".
                # In that mode, if I am just wrapping it on a pipe, it will look like a pipe.
                # Maybe the warpPolar logic distorted it?
                
                # Actually, simply resizing 640x480 to 320x240 maintains 4:3.
                # If the user wants 1:1, we should probably output a square video stream?
                # But standard video is often 4:3 or 16:9.
                
                # Let's just standardise to 320x240 for now as requested by previous tasks.
                # To fix the user's specific "1:1 not showing as 1:1" issue:
                # The user likely sees the image stretched.
                # If the renderer output is 640x480, and I resize to 320x240, aspect is preserved.
                # If the 1024x1024 texture looks wrong on the pipe, that's a UV issue.
                # If the user expects the *entire screen* to be 1:1, I need to change the render resolution.
                
                # Let's assume the user wants the final video feed to respect the source aspect ratio if possible,
                # OR they are complaining that the 1024x1024 texture is squashed.
                
                # CRITICAL FIX: The previous resize was blind `cv2.resize(img, (320, 240))`.
                # If the render output `img` is 640x480, this is fine.
                # If `img` were 1:1, it would squash.
                # RenderEngine is hardcoded to 640x480.
                
                # The issue is likely that the simulator *always* produces 4:3.
                # If the user wants 1:1, we should probably crop the 640x480 to 480x480? 
                # Or change RenderEngine to 480x480?
                # Changing RenderEngine resolution might break other things.
                
                # Let's add Letterboxing logic here to handle ANY aspect ratio safely,
                # fitting it into the 320x240 target for UDP.
                # No, wait. The target 320x240 IS 4:3. 
                # If I put a 1:1 image in there, I must add black bars on sides (Pillarbox).
                
                # Let's implement smart resize that preserves aspect ratio.
                
                target_w, target_h = 320, 240
                h, w = img.shape[:2]
                scale = min(target_w/w, target_h/h)
                new_w = int(w * scale)
                new_h = int(h * scale)
                
                resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                
                # Create black canvas
                img_small = np.zeros((target_h, target_w, 3), dtype=np.uint8)
                
                # Center the image
                x_offset = (target_w - new_w) // 2
                y_offset = (target_h - new_h) // 2
                
                img_small[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized
                
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
        elif cmd_id == 0x11: # Toggle Real Photo Mode
            if self.renderer:
                self.renderer.real_photo_mode = not self.renderer.real_photo_mode
                print(f"Real Photo Mode: {self.renderer.real_photo_mode}")
        elif cmd_id == 0x12: # Snapshot
            self.snapshot_request = True
            print("Snapshot requested")
        elif cmd_id == 0x13: # Toggle Recording
            self.recording = not self.recording
            print(f"Recording: {self.recording}")

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
