import os
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader('templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

template = env.get_template('index.html')

if not os.path.exists('static'):
    os.mkdir('static')

with open('data.yml', 'r') as f:
    data = yaml.load(f, Loader=yaml.BaseLoader)

service_status = {}
for event in reversed(data.get('current', [])):
    for product in event.get('products', []):
        service_status[product] = event.get('what', 'operational')

data['service_status'] = service_status

with open('static/index.html', 'w') as f:
    f.write(template.render(**data))
print('Created static/index.html')
