from jinja2 import Environment, PackageLoader
from copy import copy


def parseColor(color):
    red = int(color[0:2], 16)
    green = int(color[2:4], 16)
    blue = int(color[4:6], 16)
    if len(color) > 6:
        alpha = int(color[6:8], 16)
    else:
        alpha = 255
    return (red, green, blue, int(alpha * 100 / 255.0))


def render_mapfile(layers, config):
    layer_data = []
    for layer, component_layers in layers.items():
        for component_layer in component_layers:
            red, green, blue, alpha = parseColor(component_layer['color'])
            component_layer.update({'red': red, 'green': green, 'blue': blue, 'alpha': alpha})
            layer_data.append(component_layer)
    env = Environment(loader=PackageLoader('buildmap', 'templates'))
    template = env.get_template('map.jinja')
    return template.render(layers=layer_data, config=config)
