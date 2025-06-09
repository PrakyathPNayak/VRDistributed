from test2 import UrsinaScreenTexture
from ursina import Ursina, Entity, color, Texture
from PIL import Image
import numpy as np
import os

# Create the Ursina app
app = Ursina()

# Create a cube entity
box = Entity(
    model='cube',
    color=color.white,
)

# Create and save blank PNG
blank_image = Image.fromarray(
    np.zeros((1080, 1920, 4), dtype=np.uint8), 
    mode='RGBA'
)

# Save image and create texture from file path
texture_path = 'blank_texture.png'
blank_image.save(texture_path, 'PNG')
blank_texture = Texture(texture_path)
box.texture = blank_texture

# Create screen texture handler
screen_texture = UrsinaScreenTexture(
    entity=box,
    update_rate=60
)

def update():
    screen_texture.update_texture()

# Run the app
app.run()

# Cleanup temporary texture file on exit
if os.path.exists(texture_path):
    os.remove(texture_path)