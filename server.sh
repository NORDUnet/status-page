#!/bin/sh

cd static || exit 2
python3 -m http.server
