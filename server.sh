#!/bin/sh

. venv/bin/activate
FLASK_ENV=development FLASK_APP=status-app flask run
