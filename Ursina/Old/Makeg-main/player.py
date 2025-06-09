from ursina import *
from ursina.prefabs.health_bar import HealthBar
import guns,enemy


class Player(Entity):
    def __init__(self, **kwargs):
        super().__init__(scale=1)
        self.speed = 20
        self.height = 2
        self.momentum=2
        self.camera_pivot = Entity(parent=self, y=self.height)
        self.collision=True
        camera.parent = self.camera_pivot
        camera.position = (0,0,0)
        camera.rotation = (0,0,0)
        camera.fov = 90
        mouse.locked = True
        self.mouse_sensitivity = Vec2(40, 40)

        self.gravity = 1
        self.grounded = False
        self.jump_height = 5
        self.jump_up_duration = .5
        self.fall_after = .35  #player will fall down within this time 
        self.jumping = False
        self.air_time = 0

        self.traverse_target = scene     
        self.ignore_list = [self,]
        self.on_destroy = self.on_disable
        
        
        #player atributes
        self.enemies=[]
        for enemy in self.enemies:  #to keep enemies rendered and to make sure they dont despawn
            enemy.reset_pos()
            enemy.enable()
        #crosshair
        self.crosshair = Entity(model = "quad", color = color.black, parent = camera, rotation_z = 45, position = (0, 0, 0), scale = 0.5, z = 100, always_on_top = True)
        mouse.position=Vec3(0,0,0)
        mouse.locked=True
        #abilities
        self.health=50
        self.ability=10
        self.healthbar=HealthBar(self.health,bar_color=color.red,always_on_top=True,position=Vec2(-0.88,0.45),parent=camera.ui,scale=Vec2(0.35,0.015))
        self.healthbar.text_entity.disable()
        self.score=0 
        self.score_board=Text(str(self.score),position=Vec2(-0.88,0.4),parent=camera.ui)
        #weapons
        self.sniper=guns.rifle()
        self.sniper.color=color.black
        #melee weapon
        self.knife=guns.melee()
        self.weapons=[self.knife,self.sniper]
        self.currentweapon=0
         

        for key, value in kwargs.items():
            setattr(self, key ,value)

        # make sure we don't fall through the ground if we start inside it
        if self.gravity:
            ray = raycast(self.world_position+(0,self.height,0), self.down, traverse_target=self.traverse_target, ignore=self.ignore_list)
            if ray.hit:
                self.y = ray.world_point.y


    def update(self):
        self.score_board.text=str(self.score)
       #disable player is low health or update his health
        if self.health<=0:
            self.disable()
        else:
            self.healthbar.value = self.health
    
        #camera movement
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity[1]
        self.camera_pivot.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity[0]
        self.camera_pivot.rotation_x= clamp(self.camera_pivot.rotation_x, -90, 90)
        #resets player 
        if self.y <= -100:
            self.position = (-60, 15, -16)
            self.rotation_y = -270
            
       #movement of player mechanics
        self.direction = Vec3(
            self.forward * (held_keys['w'] - held_keys['s'])
            + self.right * (held_keys['d'] - held_keys['a'])
            ).normalized()

        feet_ray = raycast(self.position+Vec3(0,0.5,0), self.direction, traverse_target=self.traverse_target, ignore=self.ignore_list, distance=.5, debug=False)
        head_ray = raycast(self.position+Vec3(0,self.height-.1,0), self.direction, traverse_target=self.traverse_target, ignore=self.ignore_list, distance=.5, debug=False)
        if not feet_ray.hit and not head_ray.hit:
            move_amount = self.direction * self.speed
            if raycast(self.position+Vec3(-.0,1,0), Vec3(1,0,0), distance=0.5, traverse_target=self.traverse_target, ignore=self.ignore_list).hit:
                move_amount[0] = min(move_amount[0], 0)
            if raycast(self.position+Vec3(-.0,1,0), Vec3(-1,0,0), distance=0.5, traverse_target=self.traverse_target, ignore=self.ignore_list).hit:
                move_amount[0] = max(move_amount[0], 0)
            if raycast(self.position+Vec3(-.0,1,0), Vec3(0,0,1), distance=0.5, traverse_target=self.traverse_target, ignore=self.ignore_list).hit:
                move_amount[2] = min(move_amount[2], 0)
            if raycast(self.position+Vec3(-.0,1,0), Vec3(0,0,-1), distance=0.5, traverse_target=self.traverse_target, ignore=self.ignore_list).hit:
                move_amount[2] = max(move_amount[2], 0)
       
            self.position += move_amount * self.momentum * time.dt

        if self.gravity:
            # gravity
            ray = raycast(self.world_position+(0,self.height,0), self.down, traverse_target=self.traverse_target, ignore=self.ignore_list)
            
            if ray.distance <= self.height+.1:
                if not self.grounded:
                    self.land()
                self.grounded = True
                # make sure it's not a wall and that the point is not too far up
                if ray.world_normal.y > .7 and ray.world_point.y - self.world_y < .5: # walk up slope
                    self.y = ray.world_point[1]
                return
            else:
                self.grounded = False

            # if not on ground and not on way up in jump, fall
            self.y -= min(self.air_time, ray.distance-.05) * time.dt * 100
            self.air_time += time.dt * .25 * self.gravity


    def input(self, key):
        if key=='k':
            self.score+=100
        if key == 'space':
            self.jump()
        try:
            self.currentweapon=int(key)-1
            self.switch_weapon()
        except ValueError: pass
        if key=='scroll up':
            self.currentweapon=(self.currentweapon+1)%len(self.weapons)
            self.switch_weapon()    
        if key=='scroll down':
            self.currentweapon=(self.currentweapon-1)%len(self.weapons)
            self.switch_weapon()   
        
    def switch_weapon(self):
        for i,v in enumerate(self.weapons):
            if i==self.currentweapon:
                v.visible=True
                v.enabled=True
                v.equiped=True
            else:
                v.visible=False
                v.enabled=False
                v.equiped=False
    
    def jump(self):
        if not self.grounded:
            return

        self.grounded = False
        self.animate_y(self.y+self.jump_height, self.jump_up_duration, resolution=int(1//time.dt), curve=curve.out_expo)
        invoke(self.start_fall, delay=self.fall_after)
        
    def animate_text(self, text, top = 1.2, bottom = 0.6):
        text.animate_scale((top, top, top), curve = curve.out_expo)
        invoke(text.animate_scale, (bottom, bottom, bottom), delay = 0.4)       

    def start_fall(self):
        self.y_animator.pause()
        self.jumping = False

    def land(self):
        # print('land')
        self.air_time = 0
        self.grounded = True


    def on_enable(self):
        mouse.locked = True
        

    def on_disable(self):
        mouse.locked = False
        print_on_screen("Try Again",scale=2,duration=10)
        print_on_screen('score:',self.score,scale=2)
        destroy(self)
