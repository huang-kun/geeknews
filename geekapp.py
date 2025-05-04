import os
import json
import subprocess

from flask import Flask, make_response
from flask import request

from geeknews.manager import GeeknewsManager
from geeknews.utils.date import GeeknewsDate

from geeknews.notifier.email_notifier import GeeknewsEmailNotifier
from geeknews.configparser import GeeknewsConfigParser
from geeknews.config import GeeknewsEmailConfig, GeeknewsWechatPPConfig

from geeknews.notifier.wechatpp.client.client import WppClient
from geeknews.notifier.wechatpp.client.base import WppRequest, WppBaseClient
from geeknews.notifier.wechatpp.api.draft import *
from geeknews.notifier.wpp_notifier import WppNotifier

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

# post json
@app.route("/api/run_hn_and_post", methods=['POST'])
def run_hn_and_post():
    result_text = 'unknown'

    if request.method == "POST":
        params = request.get_json()
        date_compo = params.get('date', None)
        date = GeeknewsDate.now()
        if date_compo:
            compo = list(map(lambda x: int(x), filter(lambda y: y.isdigit(), date_compo.split('-'))))
            if len(compo) == 3:
                date = GeeknewsDate(compo[0], compo[1], compo[2])
        
        try:
            # run hn daily report
            geeknews_manager.hackernews_manager.generate_daily_report(date=date, override=True)
            # post to wechat public platform
            wpp_notifier = WppNotifier(
                config=GeeknewsWechatPPConfig.get_from_parser(geeknews_manager.configparser),
                hackernews_manager=geeknews_manager.hackernews_manager
            )
            wpp_notifier.post_draft(date=date)
        except Exception as e:
            result_text = str(e)
        else:
            # if run success, then check the log.
            log_path = os.path.expanduser('~/log/geeknews.log')
            process_result = subprocess.run(['tail', '-50', log_path], capture_output=True, text=True)
            if process_result.stderr:
                result_text = process_result.stderr
            elif process_result.stdout:
                result_text = process_result.stdout
            else:
                result_text = str(process_result)
    else:
        result_text = 'Not post request!'
    
    response = make_response(result_text, 200)
    response.mimetype = "text/plain"
    return response

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

# debug run:
# flask --app geekapp run