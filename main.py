from github_webhook import Webhook
from flask import Flask, jsonify
import os, json, re, requests
import heroku3
import traceback

app = Flask(__name__)
webhook = Webhook(app, secret=os.getenv("GITHUB_WEBHOOK_SECRET_TOKEN"))
# Get connection to heroku api
heroku_conn = heroku3.from_key(os.getenv('HEROKU_KEY'))

# Handle uncaught 500 Internal Server Errors
def handle_internal_server_error(e):
    print(str(e))
    traceback.print_tb(e.__traceback__)

    status = {
        'status': 'error',
        'message': str(e)
    }
    return jsonify(status), 500
app.register_error_handler(500, handle_internal_server_error)

def get_heroku_app_name(branch):
    return re.sub(r'-*$','', f'joplin-pr-{branch}'[0:30]).lower()

# Deletes a Heroku PR build if DELETION_PROTECTION is not enabled
def clean_up_app(app_name):
    try:
        heroku_app = heroku_conn.apps()[app_name]
    except KeyError:
        print(f"App {app_name} has not been built yet")
        return
    config = heroku_app.config()
    if not config["DELETION_PROTECTION"]:
        print(f"Starting to deleting app {app_name}")
        heroku_app.delete()
        print(f"Successfully deleted app {app_name}")
    else:
        print(f"DELETION_PROTECTION enabled for {app_name}, skipping clean-up.")

@app.route("/")
def hello_world():
    print('Hello World!')
    return "Hello World!"

# Define a handler for the "pull_request" event
@webhook.hook(event_type='pull_request')
def on_pull_request(data):
    action = data["action"]
    branch = data["pull_request"]["head"]["ref"]

    if (
        (action == "closed") and
        ((branch != "master") and (branch != "production"))
    ):
        app_name = get_heroku_app_name(branch)
        clean_up_app(app_name)

# Some PR build clean up jobs can slip through the cracks
# (for example, if a PR is merged or closed before the circleci build completes).
# This cron job will delete heroku PR builds that:
# 1. don't have a corresponding open PR branch and
# 2. don't have DELETION_PROTECTION enabled.
def joplin_cron_clean_up():
    print('Starting joplin clean up cron job.')
    joplin_pr_apps = [app for app in heroku_conn.apps() if app.name.startswith('joplin-pr')]
    github_res = requests.get(
        url=f"https://api.github.com/repos/cityofaustin/joplin/pulls"
    )
    pull_requests = github_res.json()
    pull_request_app_names = [get_heroku_app_name(pr["head"]["ref"]) for pr in pull_requests]

    for app in joplin_pr_apps:
        if (
            (app.name not in pull_request_app_names) and
            (not app.config()["DELETION_PROTECTION"])
        ):
            clean_up_app(app.name)

# Only needed for local development
# Zappa handles the "app" object directly
if __name__ == '__main__':
    app.run()
