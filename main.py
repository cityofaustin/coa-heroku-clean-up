from github_webhook import Webhook
from flask import Flask, jsonify
import os, json, re
import heroku3
import traceback

app = Flask(__name__)
webhook = Webhook(app, secret=os.getenv("GITHUB_WEBHOOK_SECRET_TOKEN"))

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

# Get connection to heroku api
heroku_conn = heroku3.from_key(os.getenv('HEROKU_KEY'))

# Deletes a Heroku PR build only if its
# not master
# not production
# and without DELETION_PROTECTION
def clean_up_app(branch):
    if ((branch != "master") and (branch != "production")):
        app_name = re.sub(r'-*$','', f'joplin-pr-{branch}'[0:30]).lower()
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
    print(json.dumps(data))
    action = data["action"]
    branch = data["pull_request"]["head"]["ref"]

    if (action == "closed"):
        clean_up_app(branch)

def cron_clean_up():
    print('Clean up old branches every week.')
    return "Good bye!"

# Only needed for local development
# Zappa handles the "app" object directly
if __name__ == '__main__':
    app.run()
