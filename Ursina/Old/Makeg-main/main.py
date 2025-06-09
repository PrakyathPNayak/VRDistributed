from ursina import *
from direct.stdpy import thread
import player
import enemy
import guns
import random
import os

application.asset_folder=Path(os.getcwd()+"\\assets") 
models=['AKM.glb','melee.glb','WALL_B.glb','WALL_F.glb','WALL_L.glb','WALL_R.glb']

def loader():
      for i in models:
             load_model(i)
try:
        thread.start_new_thread(function = loader, args ='')
except Exception as e:
                print("error starting thread", e)

AmbientLight(parent=scene)
DirectionalLight(shadows=True,parent=scene)
Sky()

#final setup
player1=player.Player() 
player1.position=Vec3(0,3,0)
Enemylist=[None]*2

#map
ground=Entity(model='cube',scale=(1000,10,1000),world_position=(0,0,0),collider="box",color=color.green)
left1=Entity(model='WALL_L.glb',scale=8,world_position=(-210,0,100))
left2wal=Entity(model='cube',scale=(440,4,100),world_position=(-210,0,-70),rotation=(90,90,0),collider='box',visible=False)
right2wal=Entity(model='cube',scale=(440,4,100),world_position=(190,0,-70),rotation=(90,90,0),collider='box',visible=False)
right1=Entity(model='WALL_R.glb',position=(-145,0,-90),scale=8)
front1=Entity(model='WALL_F.glb',position=(0,0,0),scale=8)#fixed
front2wal=Entity(model='cube',scale=(440,4,100),world_position=(0,0,-270),rotation=(90,180,0),collider='box',visible=False)
back1=Entity(model='WALL_B.glb',position=(0,0,-250),scale=8)
back2wal=Entity(model='cube',scale=(220,4,100),world_position=(-125,0,140),rotation=(90,180,0),collider='box',visible=False)
hiddenwal1=Entity(model='cube',scale=(220,4,100),world_position=(125,0,140),rotation=(90,180,0),collider='box',visible=False)
hiddenwal2=Entity(model='cube',scale=(70,4,100),world_position=(0,0,149),rotation=(90,180,0),collider='box',visible=False)        
for i in range(len(Enemylist)):
       Enemylist[i]=enemy.Enemy(player1)
       Enemylist[i].health+=(i/2)**2
       Enemylist[i].reset_pos()
       player1.enemies.append(Enemylist[i])  
