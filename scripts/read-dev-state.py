#!/usr/bin/env python3
"""Read exactly the dev application's state without remote backend writes."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

state = Path(os.environ['RUNNER_TEMP']) / 'flashcart-dev.tfstate'
obj = 'gcp-02-flashcart/stacks/03-application/dev/default.tfstate'
url = 'https://storage.googleapis.com/storage/v1/b/ritru-tfstate-586582398977/o/' + urllib.parse.quote(obj, safe='') + '?alt=media'
request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['ACCESS_TOKEN']})
try:
    with urllib.request.urlopen(request) as response:
        data = response.read()
    json.loads(data)
    state.write_bytes(data)
    state.chmod(0o600)
    print('Loaded existing dev application state snapshot.')
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise SystemExit(f'State snapshot fetch failed: HTTP {error.code}') from None
    state.unlink(missing_ok=True)
    print('No dev application state exists; planning a new stack locally.')
override = {'terraform': {'backend': {'local': {'path': str(state)}}}}
Path('stacks/03-application/backend_override.tf.json').write_text(json.dumps(override))
