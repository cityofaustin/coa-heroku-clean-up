from github_webhook import Webhook
from flask import Flask, jsonify
import os, json, re, requests
from distutils.util import strtobool
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


def has_deletion_protection(app):
    val = app.config()["DELETION_PROTECTION"]
    # If val is "None", return False
    if not val:
        return False
    else:
        return strtobool(val)


# Deletes a Heroku PR build if DELETION_PROTECTION is not enabled
def clean_up_app(app_name):
    try:
        heroku_app = heroku_conn.apps()[app_name]
    except KeyError:
        print(f"App {app_name} has not been built yet")
        return
    if not has_deletion_protection(heroku_app):
        print(f"Starting to delete app {app_name}")
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
            (not has_deletion_protection(app))
        ):
            clean_up_app(app.name)


def joplin_restart_production_dyno_1():
    print('Running daily production restart for Dyno 1')
    production_app = heroku_conn.app("joplin")
    dyno1 = production_app.dynos()[0]
    dyno1.restart()


# def joplin_restart_production_dyno_2():
#     print('Running daily production restart for Dyno 2')
#     production_app = heroku_conn.app("joplin")
#     dyno2 = production_app.dynos()[1]
#     dyno2.restart()


def send_translation_report():
    '''
    Runs the send_translation_report command.
    We can't set cron jobs within our Heroku dynos, so we're going to use this lambda function
    to schedule when we want to send the report.
    Schedule is set within build_zappa_settings.py.
    '''
    print("Running translation report")
    pr_app = heroku_conn.app("joplin")
    output = pr_app.run_command('python joplin/manage.py send_translation_report', attach=False, printout=True)
    print(output)


def extract_pdf_text():
    """
    Runs the extract text from pdf command
    (joplin/pages/official_documents_page/management/commands/extract_document_text.py)
    Schedule is set within build_zappa_settings.py
    """
    print("Extracting pdf text...")
    prod_app = heroku_conn.app("joplin")
    output = prod_app.run_command('python joplin/manage.py extract_document_text', attach=False, printout=True)
    print(output)


# Only needed for local development
# Zappa handles the "app" object directly
if __name__ == '__main__':
    app.run()
