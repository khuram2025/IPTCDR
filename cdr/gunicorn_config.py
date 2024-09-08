import sys

def print_to_log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

# Redirect print statements to stderr
sys.stdout = sys.stderr

# Gunicorn config
bind = "127.0.0.1:8001"
workers = 3
capture_output = True
errorlog = '-'
loglevel = 'info'

# This function will be called when Gunicorn starts
def on_starting(server):
    print("Gunicorn is starting...")

# This will be called for each worker
def post_worker_init(worker):
    print(f"Worker initialized")