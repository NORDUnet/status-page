from flask import Flask, request, redirect, abort, render_template
import yaml
from datetime import datetime, timezone


app = Flask(__name__)
data_path = 'data.yml'


def get_data():
    with open(data_path, 'r') as f:
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


@app.route('/')
def index():
    data = get_data()
    return render_template('index.html', **data)


@app.route('/edit/<event_id>', methods=['POST', 'GET'])
def edit(event_id):
    data = get_data()
    event = data['event_map'].get(event_id)
    if not event:
        abort(404)

    if request.method == 'POST':
        app.logger.info(request.form)
        return redirect('/')
    return render_template('edit.html', event=event, **data)
