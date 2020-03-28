import os
import argparse
import yaml
import mistletoe
import re
import json
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader, select_autoescape


def markdown(x):
    return mistletoe.markdown(x)


def gen_page(env, page, data, out_dir, template=None):
    if not template:
        template = page
    h = {
        'markdown': markdown,
    }
    template = env.get_template(template)
    content = template.render(h=h, **data)
    save_file(out_dir, page, content)


def save_file(out_dir, name, content):
    path = os.path.join(out_dir, name)
    with open(path, 'w') as f:
        f.write(content)
    print('Created:', path)


def atom_updated(event):
    timestamps = [event.get('start')]
    if event.get('closed'):
        now = datetime.now(timezone.utc).isoformat('T', 'seconds')
        if event.get('closed') <= now:
            timestamps.append(event.get('closed'))
    for update in event.get('updates') or []:
        if update.get('time'):
            timestamps.append(update.get('time'))
    time_pattern = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}')
    filtered_times = [t.replace(' UTC', ':00Z').replace(' ', 'T') for t in timestamps if t and time_pattern.match(t)]
    filtered_times.sort(reverse=True)
    if filtered_times:
        event['updated'] = filtered_times[0]


def atom_data(events, feed_url, entry_base_url):
    feed_data = {
        'title': 'NORDUnet Status Page',
        'url': feed_url,
        'id': feed_url,
        'updated': datetime.now(timezone.utc).isoformat('T', 'seconds'),
        'entries': [],
    }
    for event in events:
        atom_updated(event)
        event['feed_id'] = '{}{}'.format(entry_base_url, event['id'])

        feed_data['entries'].append(event)
    return feed_data


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

    # Create json feed
    json_out = {k: v for k, v in data.items() if k not in {'event_map', 'last_deploy_by'}}
    save_file(out_dir, 'feed.json', json.dumps(json_out, indent=4))

    # setup feeds
    # main feed
    feed_url = os.environ.get('FEED_URL', 'https://status.nordu.net/feed.xml')
    entry_base_url = feed_url.replace('feed.xml', '')
    all_posts = (data.get('current') or []) + (data.get('past') or [])
    feed_data = atom_data(all_posts, feed_url, entry_base_url)
    gen_page(env, 'feed.xml', feed_data, out_dir, template='atom.xml')

    # planned feed
    planned_url = feed_url.replace('feed', 'planned')
    maintenance_posts = (data.get('current') or []) + (data.get('planned') or [])
    maintenance_posts = [e for e in maintenance_posts if e.get('status') == 'maintenance']
    feed_data = atom_data(maintenance_posts, planned_url, entry_base_url)
    gen_page(env, 'planned.xml', feed_data, out_dir, template='atom.xml')


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
