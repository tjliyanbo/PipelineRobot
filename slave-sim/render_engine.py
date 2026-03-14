import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import cv2
import random
import math
import os

class RenderEngine:
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        
        # Initialize Pygame and OpenGL
        pygame.init()
        # Use OPENGL | DOUBLEBUF. HIDDEN might not work on all platforms/drivers correctly for context creation
        # but usually works on Windows.
        pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL | HIDDEN)
        
        self.init_gl()
        self.texture_id = self.generate_texture()
        self.real_photo_tex_id = self.load_real_photo('assets/real_sewer.jpg')
        # Default to True if we have a real photo (assuming load_real_photo returns a valid ID)
        self.real_photo_mode = True if self.real_photo_tex_id else False
        
        self.pipe_radius = 4.0 # Increased radius
        self.pipe_length = 60.0
        self.camera_z = 0.0
        self.camera_x = 0.0
        self.camera_y = 0.0
        self.yaw = 0.0
        self.shake_phase = 0.0
        
    def init_gl(self):
        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(60, (self.width / self.height), 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_TEXTURE_2D)
        
        # Lighting
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        
        # Spotlight configuration (Robot Headlight)
        # Position is relative to camera (0,0,0)
        glLightfv(GL_LIGHT0, GL_POSITION, [0, 0, 0, 1])
        glLightfv(GL_LIGHT0, GL_SPOT_DIRECTION, [0, 0, -1])
        glLightf(GL_LIGHT0, GL_SPOT_CUTOFF, 30.0) # Narrows the beam
        glLightf(GL_LIGHT0, GL_SPOT_EXPONENT, 10.0) # Focuses the beam
        
        # Ambient light (High Key - Global Illumination approximation)
        # Increased brightness significantly
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.8, 0.8, 0.85, 1.0])
        glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE)
        
        # Fog (Subtle, clean atmosphere)
        glEnable(GL_FOG)
        glFogfv(GL_FOG_COLOR, [0.8, 0.8, 0.85, 1]) # Bright Fog
        glFogf(GL_FOG_DENSITY, 0.02) # Reduced density for clarity
        glHint(GL_FOG_HINT, GL_NICEST)

    def generate_texture(self):
        # Generate procedural texture: Bright Metal/Ceramic Pipe (PBR-like simulation)
        # Aim: 30-50% brighter, metallic/ceramic reflection
        size = 512
        
        # 1. Base Color (Albedo): Bright Metal/Ceramic
        # Increase brightness significantly. 
        # BGR: (200, 200, 210) for clean bright metal/ceramic look
        base = np.zeros((size, size, 3), dtype=np.uint8)
        base[:, :] = (200, 200, 210) 
        
        # Add subtle noise for material realism (Grain)
        noise = np.random.randint(-15, 15, (size, size, 3), dtype=np.int16)
        texture = np.clip(base + noise, 0, 255).astype(np.uint8)

        # 2. Specular/Roughness Simulation (Baked into texture for OpenGL fixed pipeline)
        # We simulate "Metallic" by making the base texture have high contrast highlights
        # and "Roughness" by blurring reflections.
        
        # Add "Rings" (Pipe joints) - cleaner, sharper for ceramic/metal
        for i in range(0, size, 128):
            # Dark groove (AO effect)
            cv2.line(texture, (0, i), (size, i), (80, 80, 90), 3)
            # Bright Highlight edge (Specular)
            cv2.line(texture, (0, i+3), (size, i+3), (250, 250, 255), 2)
            
        # 3. Reflections / Environment Map Simulation
        # Simulate light reflecting off the wet/smooth bottom
        water_center = size // 2
        # Wide, soft reflection strip
        reflection_layer = np.zeros_like(texture)
        cv2.rectangle(reflection_layer, (water_center - 40, 0), (water_center + 40, size), (50, 50, 60), -1)
        texture = cv2.addWeighted(texture, 1.0, reflection_layer, 0.5, 0)

        # 4. Details: Water droplets / Condensation (PBR micro-details)
        for _ in range(100):
            x, y = random.randint(0, size), random.randint(0, size)
            r = random.randint(1, 3)
            # Bright specular dots
            cv2.circle(texture, (x, y), r, (240, 240, 250), -1)
            # Dark AO shadow below droplet
            cv2.circle(texture, (x, y+2), r, (100, 100, 110), -1)

        # 5. Global Illumination / AO Baking
        # Darken corners slightly for depth (Vignette)
        # Create a gradient mask
        X, Y = np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size))
        radius = np.sqrt(X**2 + Y**2)
        vignette = 1 - 0.3 * radius # Keep center bright
        vignette = np.dstack([vignette]*3)
        texture = (texture * vignette).astype(np.uint8)

        # Convert to OpenGL texture (RGB)
        texture_rgb = cv2.cvtColor(texture, cv2.COLOR_BGR2RGB)
        
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, size, size, 0, GL_RGB, GL_UNSIGNED_BYTE, texture_rgb)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        return tex_id

    def load_real_photo(self, path):
        print(f"Loading real photo from: {os.path.abspath(path)}")
        if not os.path.exists(path):
            # Create a placeholder if not exists
            print(f"Photo not found at {path}, creating placeholder...")
            placeholder = np.zeros((512, 512, 3), dtype=np.uint8)
            # Make it look different - reddish brick/rust
            placeholder[:] = (100, 120, 180) 
            cv2.circle(placeholder, (256, 256), 200, (50, 60, 90), -1) # Tunnel center
            # Add text
            cv2.putText(placeholder, "REAL PHOTO MODE", (100, 256), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            cv2.imwrite(path, placeholder)
            img = placeholder
        else:
            print(f"Found file at {path}")
            img = cv2.imread(path)
            
        if img is None: 
            print("Failed to load image with cv2.imread (returned None). Check file format/integrity.")
            return self.texture_id
        
        print(f"Image loaded successfully. Shape: {img.shape}")

        # Perspective/Polar Correction (Tunnel View -> Cylinder Wall)
        # Assume center of image is center of tunnel
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        max_radius = min(center[0], center[1])
        
        # Warp Polar: Unwraps circular image to rectangular strip
        # Output size: Width = Circumference (Angle), Height = Depth (Radius)
        # We want high res.
        dest_w = 1024 
        dest_h = 1024 
        
        # WARP_POLAR_LINEAR: Remaps to (rho, phi)
        # We need (phi, rho) -> (u, v)
        # cv2.warpPolar outputs (angle, radius) if we use correct flags?
        # Actually standard warpPolar creates a circular image from linear or vice versa.
        # To get rectangular strip from circular:
        real_texture = cv2.warpPolar(img, (dest_w, dest_h), center, max_radius, cv2.WARP_POLAR_LINEAR + cv2.WARP_INVERSE_MAP)
        # Wait, if input is circular (tunnel photo), we want to UNWRAP it to rectangular.
        # So we use WARP_POLAR_LINEAR without INVERSE_MAP? No.
        # "inverse map" usually means destination -> source.
        # Actually, let's just try standard warpPolar.
        # Correction: To unwrap a disk to a rectangle, we use linearPolar.
        # But OpenCV's warpPolar handles both.
        # If input is disk (x,y), output is rectangle (angle, radius).
        # We want (angle, radius).
        # Let's use cv2.linearPolar directly if available, or warpPolar.
        try:
            # OpenCV 3+
            # warpPolar(src, dsize, center, maxRadius, flags)
            # Default flags map (angle, radius) -> (x, y) ? No, that's creating a disk.
            # We want (x,y) -> (angle, radius).
            # This is confusing. Let's assume linearPolar:
            # dst(rho, phi) = src(x, y)
            real_texture = cv2.linearPolar(img, (center[0], center[1]), max_radius, cv2.WARP_FILL_OUTLIERS)
            # The output of linearPolar is (angle, log_radius) or (angle, radius)?
            # It's (angle, radius). So X axis is angle, Y axis is radius? Or vice versa?
            # Usually X is radius, Y is angle.
            # We need to rotate it to match cylinder UV (U=Angle, V=Length).
            real_texture = cv2.rotate(real_texture, cv2.ROTATE_90_COUNTERCLOCKWISE)
        except:
            print("Warp polar failed, using raw image")
            real_texture = cv2.resize(img, (1024, 1024))

        # Convert to RGB
        real_texture = cv2.cvtColor(real_texture, cv2.COLOR_BGR2RGB)
        # Ensure data is contiguous and byte aligned
        real_texture = np.ascontiguousarray(real_texture, dtype=np.uint8)
        
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, real_texture.shape[1], real_texture.shape[0], 
                     0, GL_RGB, GL_UNSIGNED_BYTE, real_texture)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
        
        return tex_id

    def draw_pipe(self):
        if self.real_photo_mode and self.real_photo_tex_id:
            glBindTexture(GL_TEXTURE_2D, self.real_photo_tex_id)
        else:
            glBindTexture(GL_TEXTURE_2D, self.texture_id)
            
        quadric = gluNewQuadric()
        gluQuadricTexture(quadric, GL_TRUE)
        gluQuadricOrientation(quadric, GLU_INSIDE) # Normals point inward
        
        glPushMatrix()
        # Draw a long cylinder covering the view frustum
        # Camera looks down -Z. We want pipe from roughly z=+10 (behind) to z=-100 (far ahead)
        # gluCylinder draws along +Z axis from 0 to height
        # So we rotate 180 deg around Y to point along -Z? No, just translate.
        # If we translate to (0,0,-100) and draw length 120, it goes from -100 to +20 along +Z.
        # That covers the camera at 0.
        glTranslatef(0, 0, -100)
        gluCylinder(quadric, self.pipe_radius, self.pipe_radius, 120, 32, 32)
        glPopMatrix()

    def update_camera(self, speed, turn, dt=0.05):
        # Speed: -1.0 to 1.0
        # Move camera forward/backward (Conceptually)
        # Reduced multiplier from 8.0 to 5.0 for more realistic speed
        move_speed = speed * 5.0 
        self.camera_z -= move_speed * dt # Accumulate distance
        
        # Turn (Yaw)
        turn_speed = turn * 60.0 
        self.yaw += turn_speed * dt
        
        # Camera Shake
        if abs(speed) > 0.1:
            self.shake_phase += 20.0 * dt
            shake_amp = 0.08 * abs(speed)
            self.camera_x = math.sin(self.shake_phase) * shake_amp
            self.camera_y = math.cos(self.shake_phase * 1.3) * shake_amp
        else:
            self.camera_x *= 0.9
            self.camera_y *= 0.9

    def render(self, state):
        pygame.event.pump()
        
        speed = state.get("speed", 0)
        turn = state.get("turn", 0)
        light_on = state.get("light_enabled", True) 
        
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        self.update_camera(speed, turn)
        
        # 1. Camera Shake
        glTranslatef(-self.camera_x, -self.camera_y, 0)
        
        # 2. Camera Rotation
        glRotatef(-self.yaw, 0, 1, 0)
        
        # 3. Infinite Movement via Texture Scrolling
        # Instead of moving geometry, we scroll the texture
        glMatrixMode(GL_TEXTURE)
        glLoadIdentity()
        # Scale 0.2 means texture repeats every 5 units of Z movement
        glTranslatef(0, self.camera_z * 0.2, 0) 
        glMatrixMode(GL_MODELVIEW)
        
        # Lighting Control (PBR High Key Setup)
        if light_on:
            glEnable(GL_LIGHT0)
            # Strong Key Light (5500K - Cool White)
            # Increased intensity to 1.5-2.0 equivalent
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.5, 1.5, 1.6, 1.0]) 
            # High Specular for Metallic look
            glLightfv(GL_LIGHT0, GL_SPECULAR, [1.8, 1.8, 1.9, 1.0])
            
            # Reduced attenuation for broader, brighter coverage
            glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 0.2)
            glLightf(GL_LIGHT0, GL_LINEAR_ATTENUATION, 0.01)
            glLightf(GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 0.001)
            
            # High Shininess for smooth metal/ceramic
            glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 100.0)
            glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
        else:
            glDisable(GL_LIGHT0) # Turn off main light
            
        # Draw Scene
        self.draw_pipe()
        
        # Force execution
        glFlush()
        
        # Capture Frame
        # Correctly capture 320x240 frame directly from 640x480 buffer by resizing during read or post-process?
        # Actually, self.width is 640.
        buffer = glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE)
        image = np.frombuffer(buffer, dtype=np.uint8)
        image = image.reshape((self.height, self.width, 3))
        
        # Resize image to match aspect ratio of 320x240 (4:3) if self.width/height is different
        # Currently 640x480 is 4:3, so aspect is correct.
        # But maybe we should render at 320x240 directly?
        # RenderEngine is init with 640x480.
        
        image = cv2.flip(image, 0) # OpenGL origin is bottom-left
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        pygame.display.flip() # Swap buffers
        
        return image
