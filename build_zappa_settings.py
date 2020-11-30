import os, json

zappa_settings = {
  "staging": {
    "project_name": "coa-joplin-build-cleanup",
    "s3_bucket": "coa-zappa-build",
    "app_function": "main.app",
    "runtime": "python3.7",
    "profile_name": "default",
    "environment_variables": {
      "GITHUB_WEBHOOK_SECRET_TOKEN": os.getenv("GITHUB_WEBHOOK_SECRET_TOKEN"),
      "HEROKU_KEY": os.getenv("HEROKU_KEY"),
    },
    "events": [
        {
            # Clean up Joplin PR builds that don't have an open PR. (Runs every day at midnight)
            "function": "main.joplin_cron_clean_up",
            "expression": "cron(0 5 * * ? *)"
        },
        {
            # Restart First Production dyno every day midnight (5AM UTC)
            "function": "main.joplin_restart_production_dyno_1",
            "expression":  "cron(0 5 * * ? *)"
        },
        # TODO: when/if we have a second dyno, run a function to restart that a half hour later.
        # {
        #     "function": "main.joplin_restart_production_dyno_2",
        #     "expression":  "cron(30 5 * * ? *)"
        # },
        {
            # Send translation report every Monday and Wednesday at 6AM CT (11AM UTC)
            "function": "main.send_translation_report",
            "expression":  "cron(0 11 ? * MON,WED *)"
        },
        {
            # run extract script every saturday at 6AM CT (11AM UTC)
            "function": "main.extract_pdf_text",
            "expression": "cron(0 11 ? * SAT *)"
        }
    ],
    "keep_warm": False,
  }
}

zappa_settings_file = os.path.join(os.path.dirname(__file__), 'zappa_settings.json')
with open(zappa_settings_file, 'w+', encoding='utf-8') as outfile:
    json.dump(zappa_settings, outfile, ensure_ascii=False, indent=4)
