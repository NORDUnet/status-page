#!/bin/sh
. venv/bin/activate
FILE=${1:-data.yml}
echo "Watching ${FILE} for changes"
python status.py --data "$FILE" --dev
fswatch -o --event PlatformSpecific "$FILE" | xargs -I{} -- python status.py --data "$FILE" --dev
