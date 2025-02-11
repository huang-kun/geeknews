import os, sys
import argparse
import json

from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.utils.md2html import MarkdownRenderer

from geeknews.llm import LLM
from geeknews.notifier.email_notifier import GeeknewsEmailNotifier
from geeknews.configparser import GeeknewsConfigParser
from geeknews.config import GeeknewsEmailConfig, GeeknewsWechatPPConfig

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.manager import HackernewsManager

from geeknews.manager import GeeknewsManager    

from geeknews.notifier.wechatpp.client.client import WppClient
from geeknews.notifier.wechatpp.client.base import WppRequest, WppBaseClient
from geeknews.notifier.wechatpp.api.draft import *
from geeknews.notifier.wpp_notifier import WppNotifier


class GeeknewsCommandHandler:

    def __init__(self, geeknews_manager: GeeknewsManager):
        self.geeknews_manager = geeknews_manager

    def create_parser(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(title='功能')

        # hacker news
        hackernews_parser = subparsers.add_parser('hackernews', help='Hacker News top stories')
        hackernews_parser.add_argument('--fetch', action='store_true', help='是否获取每日热点')
        hackernews_parser.add_argument('--report', action='store_true', help='生成markdown报告')
        hackernews_parser.add_argument('--render', help='Markdown渲染为HTML')
        hackernews_parser.add_argument('--send', action='store_true', help='是否发送测试邮件')
        hackernews_parser.set_defaults(func=self.generate_hacker_news_daily_report)

        email_parser = subparsers.add_parser('email', help='邮箱管理')
        email_parser.add_argument('--send', action='store_true', help='发送当天的html给所有beta用户')
        email_parser.add_argument('--list', action='store_true', help='列出所有beta用户的邮箱')
        email_parser.add_argument('--add', help='添加邮箱')
        email_parser.add_argument('--merge', help='从文件里批量添加邮箱列表')
        email_parser.add_argument('--remove', help='删除邮箱')
        email_parser.set_defaults(func=self.handle_email)

        wpp_parser = subparsers.add_parser('wpp', help='公众号接口测试')
        wpp_parser.add_argument('--get-drafts', action='store_true', help='批量获取草稿')
        wpp_parser.add_argument('--get-materials', action='store_true', help='获取素材列表')
        wpp_parser.add_argument('--post', action='store_true', help='发布公众号文章草稿')
        wpp_parser.set_defaults(func=self.handle_wechat_public_platform)

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
            if override or (not override and not os.path.exists(report_path)):
                hackernews_manager.generate_daily_report(locale=locale, date=date, override=override)
            if os.path.exists(report_path):
                LOG.info(f"[终端任务执行完毕] {report_path}") 
            else:
                LOG.error("[终端任务]汇总结束, 未发现任何报告")
        
        elif args.report:
            hackernews_manager.report_writer.generate_report('topstories', locale, date, override)

        elif args.render:
            markdown_path = args.render

            if not isinstance(markdown_path, str) or not os.path.exists(markdown_path):
                LOG.error(f"[终端任务]渲染失败, 文件路径无效{markdown_path}")
                return
            if not markdown_path.endswith('.md'):
                LOG.error(f"[终端任务]渲染失败, 文件格式要求是.md")
                return
            
            md_basename = os.path.basename(markdown_path)
            md_name, _ = os.path.splitext(md_basename)
            md_name_suffix = md_name.split('.')[-1] if '.' in md_name else ''
            
            renderer = MarkdownRenderer()
            html = renderer.generate_html_from_md_path(
                markdown_path=markdown_path,
                action='mistune',
                title='Geeknews',
                footer='2025. Geeknews',
                css_inline_flag=bool(md_name_suffix),
            )
            renderer.clean_all_caches()

            markdown_dir = os.path.dirname(markdown_path)
            basename = os.path.basename(markdown_path)
            filename, _ = os.path.splitext(basename)
            if md_name_suffix and not filename.endswith(md_name_suffix):
                filename = filename + '.' + md_name_suffix
            html_path = os.path.join(markdown_dir, filename+'.html')
            
            with open(html_path, 'w') as f:
                f.write(html)

            LOG.debug(f"[终端任务]渲染完成 {html_path}")
        
        elif args.send:
            LOG.info('[开始执行终端任务]发送Hacker News测试邮件')
            
            if not os.path.exists(report_path):
                LOG.error("[终端任务]无法发送邮件, 未发现任何报告")
                return
            
            with open(report_path) as f:
                report_html = f.read()
            
            story_title = hackernews_manager.get_daily_top_story_title(locale, date)
            final_title = f'HN热点: {story_title}' if story_title else 'Hacker News 热点汇总'

            email_notifier.dry_run = False
            email_notifier.notify(title=final_title, content=report_html, debug=True)

            LOG.info(f"[终端任务执行完毕] {report_path}") 

    def handle_email(self, args):
        hackernews_manager = self.geeknews_manager.hackernews_manager
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

            story_title = hackernews_manager.get_daily_top_story_title(locale, date)
            final_title = f'HN热点: {story_title}' if story_title else 'Hacker News 热点汇总'
            
            email_notifier.dry_run = False
            email_notifier.notify(title=final_title, content=report_html, debug=False)
        
        elif args.list:
            emails = email_notifier.beta_testers
            if not emails:
                emails = email_notifier.load_tester_emails()
            print(json.dumps(emails, ensure_ascii=False, indent=4))

        elif args.add:
            email_notifier.add_tester_email(args.add)

        elif args.merge:
            email_notifier.merge_tester_emails(args.merge)
        
        elif args.remove:
            email_notifier.remove_tester_email(args.remove)


    def handle_wechat_public_platform(self, args):
        llm = None
        configparser = GeeknewsConfigParser()
        hackernews_config = HackernewsConfig.get_from_parser(configparser)
        hackernews_dpm = HackernewsDataPathManager(hackernews_config)
        
        hackernews_manager = HackernewsManager(llm, hackernews_config, hackernews_dpm)

        wpp_config = GeeknewsWechatPPConfig.get_from_parser(configparser)
        wpp_client = WppClient(wpp_config)
        wpp_notifier = WppNotifier(
            config=wpp_config,
            hackernews_manager=hackernews_manager
        )

        if args.get_drafts:
            print(wpp_client.batch_get_drafts())
        elif args.get_materials:
            print(wpp_client.batch_get_material())
        elif args.post:
            print(wpp_notifier.post_draft())
        else:
            print('Not supported yet.')


def start_command_tool():
    manager = GeeknewsManager()
    handler = GeeknewsCommandHandler(manager)
    parser = handler.create_parser()
    args = parser.parse_args()
    args.func(args)