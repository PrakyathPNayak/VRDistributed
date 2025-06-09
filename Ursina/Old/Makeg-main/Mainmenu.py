from ursina import *
import player
import enemy
game=Ursina(title='Game',Fullscreen=True)
class MenuButton(Button):
    def __init__(self, text='', **kwargs):
        super().__init__(text, scale=(.25, .075), highlight_color=color.azure, **kwargs)

        for key, value in kwargs.items():
            setattr(self, key ,value)

button_spacing = .075 * 1.25
menu_parent = Entity(parent=camera.ui, y=.15)
main_menu = Entity(parent=menu_parent)
load_menu = Entity(parent=menu_parent)
options_menu = Entity(parent=menu_parent)
background = Entity(parent=menu_parent, model='quad', texture='shore', scale=(camera.aspect_ratio,1), color=color.white, z=1, world_y=0)

state_handler = Animator({
    'main_menu' : main_menu,
    'load_menu' : load_menu,
    'options_menu' : options_menu,
    })

def start_game():
    background.disable()
    main_menu.disable()
    import main
    


# load menu content
# main menu content
main_menu.buttons = [
    MenuButton('start game', on_click=start_game),
    MenuButton('settings', on_click=Func(setattr, state_handler, 'state', 'options_menu')),
    MenuButton('quit', on_click=Func(sys.exit)),
]
for i, e in enumerate(main_menu.buttons):
    e.parent = main_menu
    e.y = (-i-2) * button_spacing


# options menu content
review_text = Text(parent=options_menu, x=0, y=.25, text='Note:Mouse sensitivy *dpi is your edpi. Preferred to have edpi \nbetween 800 to 1200 for new players', origin=(0,0),color=color.black)
controls_text = Text(parent=options_menu, x=0,y=0.08,  text='Controls \n\n W-Forward \t S-Backward \t A-Left \t D-Right \n\n Right mouse button-Fire \t Left mouse button -ADS \n\n (1-3) or Scroll -Weapon Switch \n\n', origin=(0,0),color=color.black)
sensitivity_slider = Slider(0, 2, default=1, step=.1, dynamic=True, text='Mouse sensitivity',parent=options_menu, x=0)
sensitivity_slider.label.color=color.black
volume_slider = Slider(0, 1, default=Audio.volume_multiplier, step=.1, text='Master Volume:', parent=options_menu, x=0,color=color.black)
volume_slider.label.color=color.black
def set_volume_multiplier():
    Audio.volume_multiplier = volume_slider.value
volume_slider.on_value_changed = set_volume_multiplier

options_back = MenuButton(parent=options_menu, text='Back', x=-.25, origin_x=-.5, on_click=Func(setattr, state_handler, 'state', 'main_menu'))

for i, e in enumerate((sensitivity_slider, volume_slider,options_back)):
    e.y = -i * button_spacing-0.05


# animate the buttons in nicely when changing menu
for menu in (main_menu, load_menu, options_menu):
    def animate_in_menu(menu=menu):
        for i, e in enumerate(menu.children):
            e.original_x = e.x
            e.x += .1
            e.animate_x(e.original_x, delay=i*.05, duration=.1, curve=curve.out_quad)

            e.alpha = 0
            e.animate('alpha', .7, delay=i*.05, duration=.1, curve=curve.out_quad)

            if hasattr(e, 'text_entity'):
                e.text_entity.alpha = 0
                e.text_entity.animate('alpha', 1, delay=i*.05, duration=.1)

    menu.on_enable = animate_in_menu



game.run()
