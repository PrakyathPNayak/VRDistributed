from ursina import Ursina, EditorCamera, Entity, Button, Text, color,Texture
from ursina import AmbientLight, DirectionalLight, Sky
import player
import MssWindowcap 
import multiprocessing
from panda3d.core import Texture as PandaTexture
from PIL import Image
import numpy as np

class game(Entity):
    def __init__(self):
        super().__init__()
        self.player = player.player()
        self.player.position = (0, 0, 0)
        self.player.rotation_y = 180
        self.player.scale = 1
        self.player.collider = 'box'
        self.capture=MssWindowcap.OptimizedMSSCapture()
        #texture setup 
        self.frametexture = PandaTexture()
        self.frametexture.setup_2d_texture(
            1920, 1080, PandaTexture.T_unsigned_byte, PandaTexture.F_rgb
        )
        self.frametexture.set_minfilter(PandaTexture.FT_nearest)
        self.frametexture.set_magfilter(PandaTexture.FT_nearest)
        self.frametexture.set_wrap_u(PandaTexture.WM_clamp)
        self.frametexture.set_wrap_v(PandaTexture.WM_clamp)
        self.texture_width = 1920  # Fixed smaller size for speed
        self.texture_height = 1080
        # Pre-allocate frame buffer
        self.frame_data_size = self.texture_width * self.texture_height * 3
        self.frame_buffer = bytearray(self.frame_data_size)
        #start capture 
        self.capture.start_capture()
        self.spawn_entities()
   
    def spawn_entities(self):
        # Create a simple ground
        ground = Entity(model='plane', scale=(25, 5, 25), color=color.white, collider='box')
        origin=Entity(model='cube', position=(0, 0, 0), color=color.black, scale=(0.1, 0.1, 0.1), collider='box')
        #self.panel=Entity(model='cube', position=(1, 1, 1),rotation=(90,0,0), scale=(1.5, 0.05, 1), color=color.black, collider='box')
        self.panel1=Entity(model='cube', position=(1, 1, 1),rotation=(90,0,0), scale=(1.5, 0.0, 1), color=color.white, collider='box')
        self.panel1.model.setTexture(self.frametexture)
        # Add a button to quit the game
        #quit_button = Button(text='Quit', position=(0.85, -0.45), scale=(0.1, 0.05), on_click=self.quit_game)
   
    def updateframe(self):
        frame = self.capture.get_latest_frame()
        if frame is None:
            return
        
        # Minimal processing - direct resize if needed
        if frame.shape[:2] != (self.texture_height, self.texture_width):
            pil_img = Image.fromarray(frame[:, :, :3])
            #pil_img = pil_img.resize((self.texture_width, self.texture_height), Image.NEAREST)
            frame = np.array(pil_img)
        else:
            frame = frame[:, :, :3]
        
        # Direct memory copy
        #flipped = np.flipud(frame).astype(np.uint8)
        self.frametexture.set_ram_image(frame.tobytes())
        self.panel1.model.setTexture(self.frametexture)
          
    def quit_game(self):
        self.capture.stop_capture()
        self.quit()
try:
    from panda3d.core import loadPrcFileData
    
    # Performance optimizations using proper PRC configuration
    loadPrcFileData("", "threading-model Cull/Draw")     # Enable threading
    loadPrcFileData("", "framebuffer-multisample 0")     # Disable MSAA
    loadPrcFileData("", "want-tk false")                 # Disable Tkinter
        
except Exception as e:
    print(f"Could not apply Panda3D optimizations: {e}")
    
app= Ursina(vsync=False,fullscreen=False,borderless=True,title="VRDistributed")
app.game = game()
#main update called every frame
def update():
    app.game.updateframe()
#p1= multiprocessing.Process(target=update)
#p1.start()
#p1.join()
#decoration for the gamespace
AmbientLight(parent=app.game)
DirectionalLight(shadows=True,parent=app.game)
Sky()
#execution of the game 
app.run()