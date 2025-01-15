import os, sys
import argparse
import json

from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate

from geeknews.llm import LLM
from geeknews.notifier.email_notifier import GeeknewsEmailNotifier
from geeknews.configparser import GeeknewsConfigParser
from geeknews.config import GeeknewsEmailConfig

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.manager import HackernewsManager

from geeknews.manager import GeeknewsManager    


class GeeknewsCommandHandler:

    def __init__(self, geeknews_manager: GeeknewsManager):
        self.geeknews_manager = geeknews_manager

    def create_parser(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(title='功能')

        # hacker news
        hackernews_parser = subparsers.add_parser('hackernews', help='Hacker News top stories')
        hackernews_parser.add_argument('--fetch', action='store_true', help='是否获取每日热点')
        hackernews_parser.add_argument('--send', action='store_true', help='是否发送测试邮件')
        hackernews_parser.set_defaults(func=self.generate_hacker_news_daily_report)

        email_parser = subparsers.add_parser('email', help='邮箱管理')
        email_parser.add_argument('--send', action='store_true', help='发送当天的html给所有beta用户')
        email_parser.add_argument('--list', action='store_true', help='列出所有beta用户的邮箱')
        email_parser.add_argument('--add', help='添加邮箱')
        email_parser.add_argument('--remove', help='删除邮箱')
        email_parser.set_defaults(func=self.handle_email)

        return parser

    def generate_hacker_news_daily_report(self, args):
        hackernews_manager = self.geeknews_manager.hackernews_manager
        hackernews_dpm = self.geeknews_manager.hackernews_dpm
        email_notifier = self.geeknews_manager.email_notifier

        locale = 'zh_cn'
        date = GeeknewsDate.now()
        override = True
        
        report_path = hackernews_dpm.get_report_file_path(locale=locale, date=date, ext='.html')

        if args.fetch:
            LOG.info(f'[开始执行终端任务]Hacker News每日热点: {date}')
            if not os.path.exists(report_path):
                hackernews_manager.generate_daily_report(locale=locale, date=date, override=override)
            if not os.path.exists(report_path):
                LOG.error("[终端任务]汇总结束, 未发现任何报告")
                return
        
        if args.send:
            LOG.info('[开始执行终端任务]发送Hacker News测试邮件')
            if not os.path.exists(report_path):
                LOG.error("[终端任务]无法发送邮件, 未发现任何报告")
                return
            with open(report_path) as f:
                report_html = f.read()
            email_notifier.dry_run = False
            email_notifier.notify(title=f'Hacker News热点汇总: {date.formatted}', content=report_html, debug=True)

        LOG.info(f"[终端任务执行完毕] {report_path}") 

    def handle_email(self, args):
        email_notifier = self.geeknews_manager.email_notifier
        hackernews_dpm = self.geeknews_manager.hackernews_dpm
        
        email_path = email_notifier.get_email_tester_path()
        if not os.path.exists(email_path):
            LOG.error(f"[终端任务]邮箱地址文件不存在: {email_path}")
            return

        locale = 'zh_cn'
        date = GeeknewsDate.now()

        if args.send:
            report_path = hackernews_dpm.get_report_file_path(locale=locale, date=date, ext='.html')
            if not os.path.exists(report_path):
                LOG.error("[终端任务]无法发送邮件, 未发现任何报告")
                return

            with open(report_path) as f:
                report_html = f.read()
            
            email_notifier.dry_run = False
            email_notifier.notify(title=f'Hacker News热点汇总: {date.formatted}', content=report_html, debug=False)
        
        elif args.list:
            emails = email_notifier.beta_testers
            if not emails:
                emails = email_notifier.load_tester_emails()
            print(json.dumps(emails, ensure_ascii=False, indent=4))

        elif args.add:
            email_notifier.add_tester_email(args.add)
        
        elif args.remove:
            email_notifier.remove_tester_email(args.remove)


def start_command_tool():
    manager = GeeknewsManager()
    handler = GeeknewsCommandHandler(manager)
    parser = handler.create_parser()
    args = parser.parse_args()
    args.func(args)