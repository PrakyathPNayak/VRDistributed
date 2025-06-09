from ursina.prefabs import first_person_controller
from ursina import EditorCamera
from ursina import color, held_keys
class player(first_person_controller.FirstPersonController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.model = 'cube'
        self.camera_pivot.position = (0, 1, 1)
        self.color = color.white
        self.scale = 0.5
        self.collider = 'box'
        self.gravity = 0.1
        self.jump_height = 2
        self.speed = 5
        self.rotation_y = 180

    def update(self):
        super().update()
        if held_keys['shift']:
            self.speed = 10
        else:
            self.speed = 5