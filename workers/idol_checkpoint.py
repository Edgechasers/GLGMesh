"""Keep resumed latents on the sampling schedule that created them."""
import json

def check_schedule(folder,steps):
    path=folder/'sampling-schedule.json'
    cached=any((folder/name).exists() for name in ['idol-progress.pt','idol-sample.pt'])
    saved=json.loads(path.read_text())['steps'] if path.exists() else 50
    if cached and saved!=steps:
        raise ValueError('IDOL step count changed since this checkpoint. Start a new run.')
    pending=path.with_suffix('.tmp')
    pending.write_text(json.dumps({'steps':steps}))
    pending.replace(path)
