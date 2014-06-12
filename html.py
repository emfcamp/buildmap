from jinja2 import Environment, PackageLoader


def render_html_file(layers, config):
    data = {}
    for name, layers in layers.iteritems():
        data[name] = {'layer_list': ",".join(layer['name'] for layer in layers),
                      'source_file': layers[0]['source']}

    env = Environment(loader=PackageLoader('buildmap', 'templates'))
    template = env.get_template('layers-js.jinja')
    return template.render(layers=data, config=config)
