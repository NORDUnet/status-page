import os
import argparse
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


def gen_page(env, page, data, out_dir):
    path = os.path.join(out_dir, page)
    with open(path, 'w') as f:
        template = env.get_template(page)
        f.write(template.render(**data))
        print('Created:', path)


def main(out_dir, data_path, dev=False):
    base_path = os.path.dirname(os.path.abspath(__file__))
    env = Environment(
        loader=FileSystemLoader(os.path.join(base_path, 'templates')),
        autoescape=select_autoescape(['html', 'xml'])
    )

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with open(data_path, 'r') as f:
        data = yaml.load(f, Loader=yaml.BaseLoader)

    service_status = {}
    for event in reversed(data.get('current', [])):
        for product in event.get('products', []):
            service_status[product] = event.get('status', 'operational')

    data['service_status'] = service_status
    if dev:
        data['static_prefix'] = 'https://status.nordu.net'

    gen_page(env, 'index.html', data, out_dir)
    gen_page(env, 'zoom.html', data, out_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d',
        '--data',
        default='data.yml',
        help='Which data file to use when gennerating pages')
    parser.add_argument(
        '-o',
        '--out',
        default='static',
        help='Path to output directory.')
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Which data file to use when gennerating pages')

    args = parser.parse_args()
    main(args.out, args.data, args.dev)
