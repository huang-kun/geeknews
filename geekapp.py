import os
import json

from flask import Flask
from flask import request

from geeknews.manager import GeeknewsManager
from geeknews.utils.date import GeeknewsDate

app = Flask(__name__)
geeknews_manager = GeeknewsManager()

@app.route("/")
def hello_world():
    return "<p>Hello, Geeknews!</p>"

@app.route("/api/update_preview")
def update_preview():
    format, locale, date = get_preview_params()
    preview_path = geeknews_manager.hackernews_manager.generate_preview_markdown(date, locale)
    return load_preview_text(preview_path, format)

@app.route("/api/check_preview")
def check_preview():
    format, locale, date = get_preview_params()
    preview_path = geeknews_manager.hackernews_manager.get_preview_markdown_path(date, locale)
    return load_preview_text(preview_path, format)

# post form
@app.route("/api/set_stories_priority", methods=['POST'])
def set_stories_priority():
    if request.method == 'POST':
        rule_line = request.form['rule_line']
        date = GeeknewsDate.now().get_preview_date()
        rule_path = geeknews_manager.hackernews_manager.api_client.make_priority_rule(rule_line, date)
        if os.path.exists(rule_path):
            with open(rule_path) as f:
                rule_content = json.load(f)
            return rule_content
    return {}

@app.route("/api/v2/check_preview")
def check_preview_v2():
    date = GeeknewsDate.now().get_preview_date()
    preview_path = geeknews_manager.hackernews_manager.get_preview_json_path(date)
    return load_preview_json(preview_path)

@app.route("/api/v2/update_preview")
def update_preview_v2():
    _, locale, date = get_preview_params()
    preview_path = geeknews_manager.hackernews_manager.generate_preview_json(date, locale)
    return load_preview_json(preview_path)

# post json
@app.route("/api/v2/set_stories_preorder", methods=['POST'])
def set_stories_priority_v2():
    if request.method == 'POST':
        params = request.get_json()
        preorder_data = params.get('preorder', [])
        date = GeeknewsDate.now().get_preview_date()
        rule_path = geeknews_manager.hackernews_manager.api_client.make_preorder_rule(preorder_data, date)
        if os.path.exists(rule_path):
            with open(rule_path) as f:
                rule_content = json.load(f)
            return rule_content
    return {}

def get_preview_params():
    format = request.args.get('format', '')
    locale = 'zh_cn'
    date = GeeknewsDate.now().get_preview_date()
    return format, locale, date

def load_preview_text(preview_path, format):
    if os.path.exists(preview_path):
        with open(preview_path) as f:
            preview_content = f.read()
        if format == 'json':
            lines = preview_content.split('\n')
            return {"data": lines}
        else:
            return {"data": preview_content}
    return {}

def load_preview_json(preview_path):
    result = []
    if os.path.exists(preview_path):
        with open(preview_path) as f:
            result = json.load(f)
    return result