import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import cv2
import random
import math

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
        
        # Ambient light (brighter so we can see without spotlight)
        glLightModelfv(GL_LIGHT_MODEL_AMBIENT, [0.6, 0.6, 0.6, 1.0])
        glLightModeli(GL_LIGHT_MODEL_TWO_SIDE, GL_TRUE)
        
        # Fog for atmosphere/dust (lighter fog for visibility)
        glEnable(GL_FOG)
        glFogfv(GL_FOG_COLOR, [0.1, 0.1, 0.1, 1])
        glFogf(GL_FOG_DENSITY, 0.04)
        glHint(GL_FOG_HINT, GL_NICEST)

    def generate_texture(self):
        # Generate procedural concrete sewer texture
        size = 512
        # Base noise (Lighter concrete/stone)
        texture = np.random.randint(140, 190, (size, size, 3), dtype=np.uint8)
        
        # Add "rings" (pipe joints)
        for i in range(0, size, 64):
            # Dark groove
            cv2.line(texture, (0, i), (size, i), (80, 80, 80), 2)
            # Water stain / moss around joints
            stain_color = (70, 100, 70) # BGR - greenish moss
            cv2.line(texture, (0, i+2), (size, i+2), stain_color, 4)
            
        # Blur to make it look like smooth concrete
        texture = cv2.GaussianBlur(texture, (7, 7), 0)
        
        # Add random "corrosion" or "water damage" spots
        for _ in range(40):
            x, y = random.randint(0, size), random.randint(0, size)
            r = random.randint(5, 25)
            color = (random.randint(50, 100), random.randint(80, 130), random.randint(100, 150))
            cv2.circle(texture, (x, y), r, color, -1)
            
        # Add a water line at the bottom (assuming cylinder maps V around the circle)
        # Texture wraps around. Let's add a darker, greenish band for the water flow path
        cv2.rectangle(texture, (0, size - 100), (size, size), (60, 90, 80), -1)

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

    def draw_pipe(self):
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
        move_speed = speed * 8.0 
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
        
        # Lighting Control
        if light_on:
            glEnable(GL_LIGHT0)
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 0.95, 0.8, 1.0])
            glLightfv(GL_LIGHT0, GL_SPECULAR, [1.0, 1.0, 1.0, 1.0])
            # Reduced attenuation for better visibility
            glLightf(GL_LIGHT0, GL_CONSTANT_ATTENUATION, 0.1)
            glLightf(GL_LIGHT0, GL_LINEAR_ATTENUATION, 0.02)
            glLightf(GL_LIGHT0, GL_QUADRATIC_ATTENUATION, 0.002)
        else:
            glDisable(GL_LIGHT0) # Turn off main light
            
        # Draw Scene
        self.draw_pipe()
        
        # Force execution
        glFlush()
        
        # Capture Frame
        buffer = glReadPixels(0, 0, self.width, self.height, GL_RGB, GL_UNSIGNED_BYTE)
        image = np.frombuffer(buffer, dtype=np.uint8)
        image = image.reshape((self.height, self.width, 3))
        image = cv2.flip(image, 0) # OpenGL origin is bottom-left
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        pygame.display.flip() # Swap buffers
        
        return image
