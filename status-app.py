from flask import Flask, request, redirect, abort, render_template, g, url_for
from functools import wraps
import yaml
from datetime import datetime, timezone
import os


app = Flask(__name__)
DATA_PATH = os.environ.get('DATA_PATH', 'data.yml')
SECTIONS = ['current', 'info', 'planned', 'past']
VALID_USERS = set()


def str_presenter(dumper, data):
    # Only for multiline
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)


def get_data():
    with open(DATA_PATH, 'r') as f:
        data = yaml.load(f, Loader=yaml.BaseLoader)

    service_status = {}
    for event in reversed(data.get('current', [])):
        for product in event.get('products', []):
            service_status[product] = event.get('status', 'operational')

    data['service_status'] = service_status
    data['now'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M %Z')
    data['statuses'] = [
        'operational',
        'degraded',
        'outage',
        'critical',
        'maintenance',
    ]
    all_posts = []
    all_posts = all_posts + (data.get('past') or [])
    all_posts = all_posts + (data.get('planned') or [])
    all_posts = all_posts + (data.get('info') or [])
    all_posts = all_posts + (data.get('current') or [])
    data['event_map'] = {e.get('id'): e for e in all_posts}
    data['show_edit'] = True
    return data


def save_data(data):
    to_save = data.copy()
    del to_save['event_map']
    del to_save['show_edit']
    del to_save['service_status']

    to_save['now'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M %Z')
    with open(DATA_PATH, 'w') as f:
        yaml.dump(to_save, f, sort_keys=False, indent=2)


@app.before_request
def auth():
    if app.env == 'development':
        g.user = 'DevDev'
        return
    user = request.environ.get('REMOTE_USER') or request.args.get('user')
    g.user = None
    if user in VALID_USERS or not VALID_USERS:
        g.user = user


def login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    data = get_data()
    return render_template('index.html', **data)


def fields(data, starts_with):
    return {k.replace(starts_with, '', 1): data[k] for k in data if k.startswith(starts_with)}


@app.route('/edit/<event_id>', methods=['POST', 'GET'])
@login_required
def edit(event_id):
    data = get_data()
    event = data['event_map'].get(event_id)
    if not event:
        abort(404)
    # section
    event_section = None
    for section in SECTIONS:
        for e in data.get(section) or []:
            if e.get('id') == event_id:
                event_section = section
                break
        if event_section:
            break

    if request.method == 'POST':

        event_form = fields(request.form, 'event_')

        event['title'] = event_form['title']
        event['body'] = event_form['body']
        event['products'] = [p for p in request.form.getlist('event_products[]')]
        event['start'] = event_form['start']
        event['closed'] = event_form['closed']
        event['system_status'] = event_form['system_status']
        event['user_impact'] = event_form['user_impact']
        # what about status?
        # status follows user_impact, except for operational?
        event['status'] = event['user_impact']

        # updates
        event_updates = fields(event_form, 'updates_')

        update_prefixes = [u.split('_')[0] for u in event_updates if u.endswith('_title')]
        updates = []
        for prefix in update_prefixes:
            updates.append({
                'title': event_updates[prefix + '_title'],
                'time': event_updates[prefix + '_time'],
                'body': event_updates[prefix + '_body'],
            })

        # new order
        if event_form.get('new_update_title'):
            updates.append(
                {
                    'title': event_form['new_update_title'],
                    'time': event_form.get('new_update_time'),
                    'body': event_form.get('new_update_body'),
                }
            )
        updates.sort(key=lambda u: u['time'], reverse=True)
        event['updates'] = updates

        # section
        if event_form['section'] and event_section != event_form['section']:
            # seciton changed
            data[event_section].remove(event)
            data[event_form['section']].append(event)
            event_section = event_form['section']

        # cleanup
        if event_section == 'info':
            del event['start']
            del event['system_status']
            del event['user_impact']
            event['status'] = 'operational'
        save_data(data)
        return redirect(url_for('index'))

    return render_template(
        'edit.html',
        event=event,
        event_section=event_section,
        sections=SECTIONS,
        **data)


@app.route('/delete/<event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    data = get_data()

    event_section = None
    event = None
    for section in SECTIONS:
        for e in data.get(section) or []:
            if e.get('id') == event_id:
                event_section = section
                event = e
                break
        if event_section:
            break

    if event_section:
        data[event_section].remove(event)
        save_data(data)

    return redirect(url_for('index'))


@app.route('/new', methods=['POST', 'GET'])
@login_required
def new_event():
    data = get_data()
    event = {}

    if request.method == 'POST':
        next_id = int(max(data['event_map'].keys())) + 1

        event_form = fields(request.form, 'event_')
        event = {
            'id': next_id,
            'title': event_form['title'],
            'status': event_form['user_impact'],
            'system_status': event_form['system_status'],
            'user_impact': event_form['user_impact'],
            'products': [p for p in request.form.getlist('event_products[]')],
            'start': event_form['start'],
            'closed': event_form['closed'],
            'body': event_form['body'],
            'updates': [],
        }

        section = event_form.get('section') or 'current'
        data[section] = [event] + (data.get(section) or [])
        if section == 'info':
            del event['start']
            del event['system_status']
            del event['user_impact']
            event['status'] = 'operational'
        save_data(data)
        return redirect(url_for('index'))

    return render_template(
        'edit.html',
        event=event,
        sections=SECTIONS,
        **data)


@app.route('/publish', methods=['POST'])
@login_required
def publish():
    from status import main
    out_dir = 'static'
    main(out_dir, DATA_PATH)
    # write deploy time

    data = get_data()
    data['last_deploy'] = data['now']
    save_data(data)

    return redirect(url_for('index'))
