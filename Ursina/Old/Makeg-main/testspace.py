from ursina import *
from direct.stdpy import thread
from ursina.prefabs.sky import Sky
import player,enemy
ga=Ursina(title="game",borderless=True, fullscreen=False)
application.asset_folder=Path(r"C:\Users\yoy91\Desktop\makeg1\assets")
'''
def load_assets():
    models=['Ak47.obj','bullet.obj','melee.blend']
    textures=['textures/Ak_Base_color.png']
    for i in models:
        try:
            thread.start_new_thread(function = load_model, args =i)
        except Exception as e:
            print("error starting thread", e)
    for i in textures:
        try:
            thread.start_new_thread(function = load_texture, args =i)
        except Exception as e:
            print("error starting thread", e)
    '''       
 #setup
'''
enlis=[None]*3
for i in (enlis):
    i=enemy.Enemy(pla,2,2,2) 
'''
models=['AKM.glb','melee.glb','WALL_B.glb','WALL_F.glb','WALL_L.glb','WALL_R.glb']
for i in models:
            try:
                thread.start_new_thread(function = load_model, args =i)
            except Exception as e:
                print("error starting thread", e)
pla=player.Player()
pla.position=Vec3(10,2,10)
#en=enemy.Enemy(pla,2,2,2)
ground=Entity(model='cube',scale=(600,10,600),world_position=(0,-1,0),collider="box",color=color.lime)
left1=Entity(model='WALL_L.glb',scale=8,world_position=(-210,0,100))
left1wal=Entity(model='cube',scale=(440,4,100),world_position=(-210,0,-70),rotation=(90,90,0),collider='box',visible=True)

left2wal=Entity(model='cube',scale=(440,4,100),world_position=(190,0,-70),rotation=(90,90,0),collider='box',visible=True)
left2=Entity(model='WALL_R.glb',position=(-145,0,-90),scale=8)
left3=Entity(model='WALL_F.glb',position=(0,0,0),scale=8)#fixed
left3wal=Entity(model='cube',scale=(440,4,100),world_position=(0,0,-270),rotation=(90,180,0),collider='box',visible=True)
left4=Entity(model='WALL_B.glb',position=(0,0,-250),scale=8)
left4wal=Entity(model='cube',scale=(220,4,100),world_position=(-125,0,140),rotation=(90,180,0),collider='box',visible=True)
left4wal2=Entity(model='cube',scale=(220,4,100),world_position=(125,0,140),rotation=(90,180,0),collider='box',visible=True)
left4wal3=Entity(model='cube',scale=(70,4,100),world_position=(0,0,149),rotation=(90,180,0),collider='box',visible=True)

mouse.visible=False


#map
#ma=Entity(model="map03.glb",collider='box',world_position=(0,0,0),scale=1.2)
#ground.tag="map"
box=Entity(model='cube',scale=(10,10,10),color=color.red,world_position=(1,10,1),collider="box")
box.tag='enemy'
box.health=100
box2=Entity(model='cube',scale=(20,10,20),color=color.black,world_position=(20,20,1),collider="box")

def update():
    
    if box.hovered:
        box.color=color.white
    else:
        box.color=color.red    
    if box.health<=0:
        destroy(box)
def input(key):   
    if key=='u':
        print_on_screen(pla.position,position=(0,0,5))      
    else:
        pass
ga.run()    