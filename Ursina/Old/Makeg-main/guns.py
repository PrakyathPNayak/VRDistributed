from ursina import *
from ursina import curve
class gun (Entity):
    def __init__(self,**kwargs):
     super().__init__(self,scale=0.25,parent=camera.ui,position=(0.7,-0.3),rotation=(0,110,0),visible=False,enabled=False,**kwargs)
     pivot=Entity(position=self.position,parent=self)
     self.firerate=0
     self.reloadtime=0
     self.tip = Entity(parent = self, position = (.7,-0.5))
     self.magazine=0
     self.inmag=int(self.magazine)
     self.guntype=""
     self.startedshooting=False
     self.equiped=False
     self.audio=Audio('AKsound.mp3',False)
    def input(self,key):
       if key=="left mouse down":
          self.audio.play()
          self.shoot()
       elif key=='left mouse up':
            invoke(setattr,self,'startedshooting',False,delay=self.firerate)
       if key=='r':
           self.reload() 
       if key=="right mouse down":
           self.scale=1
           self.animate_position((0,-1),delay=0,duration=0)
           self.animate_rotation((0,90,0),delay=0,duration=0)
           
       elif key=="right mouse up":
           self.animate_position((0.7,-0.3),duration=0,delay=0)
           self.animate_rotation((0,110,0),delay=0,duration=0)   
           self.scale=0.25     
    def update(self):
        if self.inmag<=self.magazine:
            self.reload()
        self.inmag=clamp(self.inmag,0,self.magazine)   
    def reload(self):
        self.inmag+=self.magazine
        self.animate_position(Vec2(0.4,-0.3),duration=self.reloadtime,curve=curve.linear)
        self.animate_position(Vec2(0.7,-0.3),delay=self.reloadtime,curve=curve.linear)           
    def shoot(self):
       if self.equiped:
          self.inmag-=1
          if self.guntype=='rifle' and not self.startedshooting:
             Bullet(self)
             self.animate('rotation_z',-10, duration = self.firerate, curve = curve.linear)
             self.animate('rotation_z',0, 0.4, delay =self.firerate, curve = curve.linear)
             invoke(setattr,self,'startedshooting',True,delay=self.firerate)             

class Bullet(Entity) :
    def __init__(self,gun):
       super().__init__(self,scale=0.2,parent=gun,position=gun.tip.world_position)
       self.gun=gun
       self.thickness=8
       self.rotation=camera.rotation
       self.color=color.black
       if hasattr(self.gun, 'tip'):
           self.rotation=camera.world_rotation
       if mouse.hovered_entity:
          self.hovered_point=mouse.hovered_entity
          self.animate("position", Vec3(self.hovered_point.world_position) + (self.forward*1000), distance(self.hovered_point.world_position + (self.forward*1000),self.gun.position) / 150, curve = curve.linear) 
          self.position += self.forward * 2000 * time.dt
       
    def update(self):
      try:
                      if mouse.hovered_entity.tag=='enemy':
                          if mouse.hovered_entity.health>0:
                              mouse.hovered_entity.health-=self.gun.dmg
                         
                          else:
                              mouse.hovered_entity.target.score+=5
                              mouse.hovered_entity.target.health+=10
                              Audio('heal.mp3').play()
                        
                              destroy(mouse.hovered_entity)  
      except AttributeError:pass
      destroy(self)
class melee(Entity):
   def __init__(self,**kwargs):
      super().__init__(self,model='melee.glb',scale=0.2,parent=camera.ui,visible=True,position=(-0.1,-0.6),rotation=(0,-20,10),**kwargs)
      self.equipped=False
      self.dmg=100
      self.tip = Entity(parent = self, position = (.7,-0.5))
      self.audio=Audio('sword.mp3',False)   
   def cut(self):
         self.audio.play()
         self.animate_position((0.2,-0.6),duration=0.2,curve=curve.linear)         
         self.animate_rotation((0,-50,-75),duration=0.2,curve=curve.linear)
         self.animate_position((0,-0.6),0.3,delay=0.2,curve=curve.linear) 
         self.animate_rotation((0,-20,10),0.45,delay=0.28,curve=curve.linear)
         self.animate_position((-0.1,-0.6),0.45,delay=0.28,curve=curve.linear) 
         Bullet(self)
   def input(self,key):
         if key=='left mouse down':
            self.cut()
   def update(self):
      if self.equipped:
            self.animate_position((-0.1,-0.4),duration=0,curve=curve.linear)
            self.animate_position((-0.1,-0.6),duration=0.2,curve=curve.linear)               
            
class rifle(gun):
   def __init__(self):
      super().__init__(model='AKM.glb')
      self.guntype="rifle"
      self.reloadtime=2.5
      self.firerate=0.05
      self.magazine=5
      self.dmg=50
             