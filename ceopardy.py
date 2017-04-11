# Ceopardy
# https://github.com/obilodeau/ceopardy/
#
# Olivier Bilodeau <olivier@bottomlesspit.org>
# Copyright (C) 2017 Olivier Bilodeau
# All rights reserved.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
import functools
import logging
import random
import re
import sys

# authentication related: commented for now
# import flask_login
from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, emit, disconnect

# authentication related: commented for now
# import ceopardy.login as login
from ceopardy.api import api
from ceopardy.controller import controller
from ceopardy.forms import TeamNamesForm, TEAM_FIELD_ID

app = Flask(__name__)
socketio = SocketIO(app)

def authenticated_only(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        if not flask_login.current_user.is_authenticated:
            disconnect()
        else:
            return f(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_config():
    """Injects ceopardy configuration for the template system"""
    return controller.get_config()


@app.route('/')
def start():
    if controller.is_game_ready():
        # TODO eventually viewer should just become /?
        return render_template("viewer.html")
    else:
        return render_template('lobby.html')


# TODO we must kill all client-side state on server load.
# To reproduce: Not-reloading a host view and reloading server causes mismatch
# between client and server states. Client is out of sync.
# authentication related: commented for now
#@flask_login.login_required
@app.route('/host')
def host():
    # Start the game if it's not already started
    if not controller.is_game_ready():
        form = TeamNamesForm()
        return render_template('host-setup.html', form=form)

    return render_template('host.html')


# TODO: kick-out if game is started
@app.route('/setup', methods=["GET", "POST"])
def setup():
    form = TeamNamesForm()
    # TODO: [LOW] csrf token errors are not logged (and return 200 which contradicts docs)
    if form.validate_on_submit():

        teamnames = [field.data for field in form if TEAM_FIELD_ID in field.flags]
        controller.start_game(teamnames)

        # announce waiting room that game has started
        emit("start_game", namespace="/wait", broadcast=True)
        return redirect('/host')

    return render_template('host-setup.html', form=form)


# TODO eventually viewer should just become /?
@app.route('/viewer')
def viewer():
    team_stats = controller.get_team_stats()
    # FIXME crashes, need to store in global context?
    # See: http://flask.pocoo.org/docs/0.12/appcontext/
    return render_template('viewer.html', team_stats=team_stats)


@socketio.on('click', namespace='/host')
def handle_click(data):
    print('received data: ' + data["id"], file=sys.stderr)
    match = re.match("c([0-9]+)q([0-9]+)", data["id"])
    if match is not None:
        items = match.groups()
        column = int(items[0])
        row = int(items[1])
        controller.set_question_solved(column, row, True)
        state = controller.dictionize_questions_solved()
        emit("update-board", state, namespace='/viewer', broadcast=True)
        emit("show-overlay", "<p>Test!</p>", namespace='/viewer', broadcast=True)


@socketio.on('unclick', namespace='/host')
def handle_click(data):
    emit("hide-overlay", namespace='/viewer', broadcast=True)


@socketio.on('roulette', namespace='/host')
# authentication related: commented for now
#@authenticated_only
def handle_roulette():
    nb = controller.get_nb_teams()
    l = []
    team = "t" + str(random.randrange(1, nb + 1))
    for i in range(12):
        l.append("t" + str(i % nb + 1))
    l.append(team)
    emit("roulette-team", l, namespace='/viewer', broadcast=True)


@socketio.on('refresh', namespace='/viewer')
def handle_refresh():
    state = controller.dictionize_questions_solved()
    emit("update-board", state)


if __name__ == '__main__':
    app.config['SECRET_KEY'] = 'Alex Trebek forever!'

    # logging
    file_handler = logging.FileHandler('ceopardy.log')
    #file_handler.setLevel(logging.INFO)
    file_handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter('{asctime} - {levelname} - {message}', style='{')
    file_handler.setFormatter(fmt)
    app.logger.addHandler(file_handler)

    # authentication related: commented for now
    #app.add_url_rule('/login', view_func=login.login, methods=['GET', 'POST'])
    #app.add_url_rule('/logout', view_func=login.logout, methods=['GET', 'POST'])
    #login.init_app(app)

    # TODO considered for removal
    # API - RESTful
    app.register_blueprint(api, url_prefix='/api')

    socketio.run(app, host="0.0.0.0", debug=True)
