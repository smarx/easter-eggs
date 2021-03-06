import json
import os
import os.path
import random
import time
import urlparse

from dropbox.client import DropboxClient, DropboxOAuth2Flow
from flask import abort, Flask, redirect, render_template, request, session, url_for
import redis
 
redis_url = os.environ['REDISTOGO_URL']
redis_client = redis.from_url(redis_url)
 
# App key and secret from the App console (dropbox.com/developers/apps)
APP_KEY = os.environ['APP_KEY']
APP_SECRET = os.environ['APP_SECRET']

app = Flask(__name__)
app.debug = True
 
# A random secret used by Flask to encrypt session data cookies
app.secret_key = os.environ['FLASK_SECRET_KEY']

# Easter variables
egg_refs = {
    'egg.jpg': 'M7Zx2HpjY285MDRrbXlrdg',
    'blue_egg.jpg': 'M7Zx2DN5Nm05M3Zqbmh3bA',
    'pastel_egg.jpg': 'M7Zx2Ho4d2w1d3B6czRubQ',
    'polka_dot_egg.jpg': 'M7Zx2DQ0YnFmMGwxcWZ0aA',
    'nest_eggs.jpg': 'M7Zx2HByb25hbmhvcXh0dA',
}

def get_url(route):
    '''Generate a proper URL, forcing HTTPS if not running locally'''
    host = urlparse.urlparse(request.url).hostname
    url = url_for(
        route,
        _external=True,
        _scheme='http' if host in ('127.0.0.1', 'localhost') else 'https'
    )

    return url

def get_flow():
    return DropboxOAuth2Flow(
        APP_KEY,
        APP_SECRET,
        get_url('oauth_callback'),
        session,
        'dropbox-csrf-token')

@app.route('/oauth_callback')
def oauth_callback():
    '''Callback function for when the user returns from OAuth.'''

    access_token, uid, extras = get_flow().finish(request.args)
    session['uid'] = uid
 
    # Extract and store the access token for this user
    redis_client.hset('tokens', uid, access_token)

    # Create folder tree, put random easter eggs in it.

    # OAuth token for the user
    token = redis_client.hget('tokens', uid)

    client = DropboxClient(token)

    # Set up the Easter hunt area!
    try:
        client.file_delete('/Yard')
    except Exception, e:
        pass

    client.add_copy_ref('M7Zx2DJjNXYxbjJsN3p6YQ','/Yard')
        
    try:
        client.file_delete('/Easter basket')
    except Exception, e:
        pass

    client.file_create_folder('/Easter basket')

    # Get flat list of paths to directories from '/Yard'
    flat_list = enumerate_yard('/Yard', client)

    # Choose 5 random places to hide eggs
    hiding_places = random.sample(flat_list, 5)

    # copy egg images into those hiding places
    keys = egg_refs.keys()

    for i in range(5):
        client.add_copy_ref(egg_refs[keys[i]], hiding_places[i] + '/' + keys[i])

    redis_client.hset('start_times', uid, time.time())

    return redirect(url_for('done'))

def enumerate_yard(path, client):
    cursor = None
    has_more = True

    paths = set()

    while has_more:
        response = client.delta(path_prefix=path, cursor=cursor)
        for path, metadata in response['entries']:
            paths.add(path)
        has_more = response['has_more']

    return paths

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return redirect(get_flow().start())

@app.route('/done')
def done(): 
    return render_template('done.html')

@app.route('/check_basket')
def check_basket():
    uid = session['uid']

    token = redis_client.hget('tokens', uid)

    client = DropboxClient(token)

    # check if /Easter basket has all five eggs
    basket_contents = set(
        os.path.split(item['path'])[1] for item in
        client.metadata('/Easter basket').get('contents'))

    if basket_contents >= set(egg_refs.keys()):
        elapsed = time.time() - float(redis_client.hget('start_times', uid))
        return render_template('found_eggs.html', seconds=('%.2f' % elapsed))
    else:
        return render_template('done.html', notyet=True)

if __name__=='__main__':
    app.run(debug=True)
