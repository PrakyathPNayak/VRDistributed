from ursina import *
from ursina.prefabs.health_bar import HealthBar
import random
class Enemy (Entity):
    def __init__(self,target,**kwargs):
     super().__init__(self,model="cube",color=color.red,**kwargs)
     self.target=target
     self.scale=1
     self.alive=True
     self.collider=BoxCollider(self,size=(1,1,1))
     self.pivot=Entity(position=self.position,parent=self)
     self.tag="enemy"
     self.health=5
     self.healthbar=HealthBar(self.health,bar_color=color.red,always_on_top=True,scale=Vec2(1,0.2),parent=self.pivot)
     self.healthbar.text_entity.disable()
     self.healthbar.billboard_setter(True)   
     self.position=(1,1,1)
     self.cooldown=True
     self.dmg=1
     self.i=0
     self.speed=0.001*random.random()
     
    def update(self):
      if self.hovered:
          self.color=color.white
      else:
          self.color=color.black   
      if self.y<=0:
         self.disable()
      else: self.healthbar.value=self.health
      self.add_script(SmoothFollow(self.target,speed=self.speed,offset=Vec3(2,2,2)))
      if distance(self.position,self.target.position)<=5:
          self.target.health-=self.dmg
   
    def reset_pos(self):
        self.position = Vec3(random.randint(-200, 100), random.randint(10, 50), random.randint(-100, 100))
    
       