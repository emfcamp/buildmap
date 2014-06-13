from jinja2 import Environment, PackageLoader


def render_html_file(layers, source_layers, config):
    data = {}
    for layer in layers:
        layer_list = ",".join(source_layer['name'] for source_layer in source_layers[layer['title']])
        data[layer['title']] = {'layer_list': layer_list,
                                'source_file': source_layers[layer['title']][0]['source'],
                                'enabled': layer.get('enabled', True)}

    env = Environment(loader=PackageLoader('buildmap', 'templates'))
    template = env.get_template('layers-js.jinja')
    return template.render(layers=data, config=config)
