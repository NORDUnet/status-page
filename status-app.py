from flask import Flask, request, redirect, abort, render_template, g, url_for, session
from functools import wraps
import yaml
from datetime import datetime, timezone
import os
import secrets
import mistletoe
SAML_ENABLE = os.environ.get('SAML_ENABLE')
if SAML_ENABLE:
    import saml2
    import saml2.config
    import saml2.client
    import saml2.metadata
    from saml2conf import SAML_CONFIG


app = Flask(__name__)
if 'SECRET_TOKEN' in os.environ:
    app.secret_key = os.environ.get('SECRET_TOKEN')
else:
    secret_key = secrets.token_hex(16)
    app.logger.info('No secret key supplied via SECRET_TOKEN env, using: %s', secret_key)
    app.secret_key = secret_key
DATA_PATH = os.environ.get('DATA_PATH', 'data.yml')
OUT_DIR = os.environ.get('OUT_DIR', 'static')
SECTIONS = ['current', 'info', 'planned', 'past']
VALID_USERS = set()


def str_presenter(dumper, data):
    # Only for multiline
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


yaml.add_representer(str, str_presenter)


def markdown(x):
    return mistletoe.markdown(x)


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
    data['h'] = {
        'markdown': markdown,
    }
    return data


def save_data(data):
    to_save = data.copy()
    del to_save['event_map']
    del to_save['show_edit']
    del to_save['service_status']
    if 'h' in to_save:
        del to_save['h']

    to_save['now'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M %Z')
    with open(DATA_PATH, 'w') as f:
        yaml.dump(to_save, f, sort_keys=False, indent=2)


def next_id(data):
    return max([int(k) for k in data['event_map']]) + 1


@app.before_request
def auth():
    if app.env == 'development':
        g.user = 'DevDev'
        return
    user = request.environ.get('REMOTE_USER') or session.get('user')
    if user and isinstance(user, list):
        user = user[0]
    g.user = None
    # Empty VALID_USERS means everyone who auths is ok
    if not VALID_USERS or user in VALID_USERS:
        g.user = user


def login_required(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            if SAML_ENABLE:
                return redirect(url_for('saml_login', next=request.path))
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function


@app.route('/admin/')
@login_required
def index():
    data = get_data()
    return render_template('index.html', **data)


def fields(data, starts_with):
    return {k.replace(starts_with, '', 1): data[k] for k in data if k.startswith(starts_with)}


@app.route('/admin/edit/<event_id>', methods=['POST', 'GET'])
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


@app.route('/admin/delete/<event_id>', methods=['POST'])
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


@app.route('/admin/new', methods=['POST', 'GET'])
@login_required
def new_event():
    data = get_data()
    event = {}

    if request.method == 'POST':

        event_form = fields(request.form, 'event_')
        event = {
            'id': next_id(data),
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
        title='Create',
        sections=SECTIONS,
        **data)


@app.route('/admin/publish', methods=['POST'])
@login_required
def publish():
    from status import main
    main(OUT_DIR, DATA_PATH)
    # write deploy time

    data = get_data()
    data['last_deploy'] = data['now']
    data['last_deploy_by'] = g.user
    save_data(data)

    return redirect(url_for('index'))


# SAML
def _saml_client():
    conf = saml2.config.Config()
    conf.load(SAML_CONFIG)
    return saml2.client.Saml2Client(config=conf)


@app.route('/saml2/login')
def saml_login():
    came_from = request.args.get('next', '/')
    if 'user' in session:
        return f'Already logged in as {session["user"]} <a href="{came_from}">Go back again</a>'
    # TODO: disco service, send to disco with entityID
    # get entityID of IDP
    saml_client = _saml_client()
    idp_entityid = 'https://idp.nordu.net/idp/shibboleth'

    reqid, info = saml_client.prepare_for_authenticate(
        entityid=idp_entityid,
    )
    # Store requid + back to url?
    session['relay_state'] = {reqid: came_from}
    # Do redir
    headers = dict(info['headers'])
    return redirect(headers['Location'])


# Assertion Consumer Service
@app.route('/saml2/acs', methods=['POST'])
def saml_acs():
    client = _saml_client()
    # Handle http post
    outstanding_queries = None
    if 'relay_state' in session:
        outstanding_queries = session['relay_state']
    authn_response = client.parse_authn_request_response(
        request.form['SAMLResponse'],
        saml2.BINDING_HTTP_POST,
        outstanding_queries
    )
    attribute_values = authn_response.get_identity()
    app.logger.debug('saml_acs authn_response: %s', attribute_values)

    # Save info to session
    session['user'] = attribute_values.get('eduPersonPrincipalName')
    # Cleanup session
    session.pop('relay_state')
    # redirect back to original place
    if authn_response.came_from:
        return redirect(authn_response.came_from)
    return redirect(url_for('index'))


# export metadata
@app.route('/saml2/metadata')
def metadata():
    # ui_info perhaps
    client = _saml_client()
    md = saml2.metadata.create_metadata_string(
        configfile=None,
        config=client.config
    )
    return md, {'Content-Type': 'text/xml'}
