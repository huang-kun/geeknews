import os, sys
import argparse
import json
import mistune

from pathlib import Path
from datetime import datetime, timedelta

from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.utils.md2html import MarkdownRenderer

from geeknews.llm import LLM
from geeknews.notifier.email_notifier import GeeknewsEmailNotifier
from geeknews.configparser import GeeknewsConfigParser
from geeknews.config import GeeknewsEmailConfig, GeeknewsWechatPPConfig

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.api_client import HackernewsClient, HN_MAX_DOWNLOADS, HN_RECENT_HOURS
from geeknews.hackernews.article_editor import count_words
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
        hackernews_parser.add_argument('--run', action='store_true', help='是否获取每日热点并生成总结报告')
        hackernews_parser.add_argument('--fetch', action='store_true', help='是否获取每日热点')
        hackernews_parser.add_argument('--preview', action='store_true', help='热点列表预览')
        hackernews_parser.add_argument('--set-priority', help='设置预览列表排序优先级：e.g. "low:1,3,4;high:7,9;action:override/append"')
        hackernews_parser.add_argument('--clean-cache', action='store_true', help='清理本地缓存的story数据')
        hackernews_parser.add_argument('--download', help='下载文章链接')
        hackernews_parser.add_argument('--read', help='读取文章内容')
        hackernews_parser.add_argument('--read-sum', help='读取文章摘要')
        hackernews_parser.add_argument('--validate', action='store_true', help='检查短文章内容的相关性')
        hackernews_parser.add_argument('--summary', help='文章总结')
        hackernews_parser.add_argument('--report', action='store_true', help='生成markdown报告')
        hackernews_parser.add_argument('--render', help='Markdown渲染为HTML')
        hackernews_parser.add_argument('--send', action='store_true', help='是否发送测试邮件')
        hackernews_parser.add_argument('--test', action='store_true', help='TEST MODE')
        hackernews_parser.add_argument('--debug', action='store_true', help='DEBUG MODE')
        hackernews_parser.set_defaults(func=self.generate_hacker_news_daily_report)

        email_parser = subparsers.add_parser('email', help='邮箱管理')
        email_parser.add_argument('--send', help='发送邮件')
        email_parser.add_argument('--list', action='store_true', help='列出所有beta用户的邮箱')
        email_parser.add_argument('--add', help='添加邮箱')
        email_parser.add_argument('--merge', help='从文件里批量添加邮箱列表')
        email_parser.add_argument('--remove', help='删除邮箱')
        email_parser.add_argument('--test', action='store_true', help='TEST MODE')
        email_parser.add_argument('--dry-run', action='store_true', help='DEBUG MODE')
        email_parser.set_defaults(func=self.handle_email)

        wpp_parser = subparsers.add_parser('wpp', help='公众号接口测试')
        wpp_parser.add_argument('--get-drafts', action='store_true', help='批量获取草稿')
        wpp_parser.add_argument('--get-materials', action='store_true', help='获取素材列表')
        wpp_parser.add_argument('--post', action='store_true', help='发布公众号文章草稿')
        wpp_parser.add_argument('--publish', action='store_true', help='发布公众号文章')
        wpp_parser.set_defaults(func=self.handle_wechat_public_platform)

        return parser
    
    def debug_log_story(self, story: dict, index: int):
        id = story.get('id', 0)
        title = story.get('title', '')
        score = story.get('score', 0)
        time = story.get('time', 0)

        date = datetime.fromtimestamp(time)
        is_recent = HackernewsClient.is_recent(time, HN_RECENT_HOURS)

        recent_text = "RECENT" if is_recent else ""
        date_text = date.strftime("%Y-%m-%d %H:%M")

        if is_recent:
            print(f"{index+1}. [{id}] {date_text} score: {score} {recent_text} {title}")

    def generate_hacker_news_daily_report(self, args):
        hackernews_manager = self.geeknews_manager.hackernews_manager
        hackernews_dpm = self.geeknews_manager.hackernews_dpm
        email_notifier = self.geeknews_manager.email_notifier

        locale = 'zh_cn'
        date = GeeknewsDate.now()
        override = True
        
        report_path = hackernews_dpm.get_report_file_path(locale=locale, date=date, ext='.html')

        if args.run:
            LOG.debug(f'[开始执行终端任务]Hacker News每日热点: {date}')
            if override or (not override and not os.path.exists(report_path)):
                hackernews_manager.generate_daily_report(locale=locale, date=date, override=override)
            if os.path.exists(report_path):
                LOG.debug(f"[终端任务执行完毕] {report_path}") 
            else:
                LOG.error("[终端任务]汇总结束, 未发现任何报告")

        elif args.fetch:
            override = False
            story_dir = hackernews_dpm.get_story_date_dir(date)
            story_ids = hackernews_manager.api_client.fetch_top_story_ids()
            story_ids = hackernews_manager.api_client.custom_rank_ids(story_ids, date=date, priority=True)
            for index, id in enumerate(story_ids):
                story_path = hackernews_dpm.get_story_file_path(id, date)
                with open(story_path) as f:
                    story = json.load(f)
                    self.debug_log_story(story, index)

        elif args.preview:
            date = date.get_preview_date()
            preview_path = hackernews_manager.get_preview(date, locale)
            print(f"热点列表预览: {preview_path}")

        elif args.set_priority:
            date = date.get_preview_date()
            rule_path = hackernews_manager.api_client.make_priority_rule(args.set_priority, date)
            print(f"更新排序规则: {rule_path}")

        elif args.clean_cache:
            hackernews_manager.api_client.clean_local_items(date)

        elif args.download:
            url = args.download
            text = hackernews_manager.article_editor.read_text_from_url(url)

            name = url.split('/')[-1] 
            download_dir = os.path.expanduser('~/Downloads')
            path = os.path.join(download_dir, name+'.txt')

            with open(path, 'w') as f:
                f.write(text)

        elif args.read:
            story_path = args.read
            content = hackernews_manager.article_editor.download_article_content_by_story_path(story_path)
            if content:
                story_dir = os.path.dirname(story_path)
                story_name = os.path.basename(story_path)
                temp_name, _ = os.path.splitext(story_name)
                temp_path = os.path.join(story_dir, f'temp_article_{temp_name}.md')
                with open(temp_path, 'w') as f:
                    f.write(content)
                print(f"文章下载完成, 临时路径: {temp_path}")

        elif args.read_sum:
            story_id = args.read_sum
            title, summary = hackernews_manager.summary_writer.find_summary_title_and_content(story_id, locale, date)
            print(f"标题: {title}")
            print(f"摘要: {summary}")

        elif args.validate:
            debug = args.debug
            word_limit = hackernews_manager.config.validate_word_count
            only_log_short = True

            short_articles = []

            article_dir = hackernews_dpm.config.article_dir
            article_dir_path = Path(article_dir)
            for article_path in article_dir_path.rglob('*.md'):
                file_path = str(article_path)
                with open(file_path) as f:
                    text = f.read()
                
                # remove comments from article
                comment_index = text.find('USER_COMMENTS:')
                if comment_index != -1:
                    text = text[:comment_index]
                else:
                    comment_index = text.find('**Reader Comments**:')
                    if comment_index != -1:
                        text = text[:comment_index]
                
                # parse title and content
                title, content = '', ''
                if '\n' in text:
                    components = text.split('\n')
                    
                    title = components[0]
                    if title.startswith('# '):
                        title = title[2:]

                    content = '\n'.join(components[1:])
                else:
                    LOG.error(f"无法解析文章标题: {file_path}")
                    continue
                
                word_count = count_words(content)
                if word_count < word_limit:
                    short_articles.append((title, content, file_path, word_count))

                mark_as_short = "[SHORT] " if word_count < word_limit else ""
                if mark_as_short:
                    if '\n' in text:
                        mark_as_short += text.split('\n')[0]
                    else:
                        mark_as_short += text[:50]
                
                if not only_log_short or mark_as_short:
                    print(f"{file_path} [{word_count}] {mark_as_short}")
            
            # validate
            if not debug and short_articles:
                print("=======")
                for title, content, file_path, word_count in short_articles:
                    if title.startswith("Show HN:") or title.startswith("Ask HN:"):
                        continue
                    score = hackernews_manager.article_editor.check_article_relevance_score(title, content)
                    failed = score < hackernews_manager.config.validation_score
                    invalid_mark = "[FAILED]" if failed else ""
                    print(f"{file_path} [{word_count}] 关联性评价得分: {score}, {invalid_mark} {title[:50]}")

        elif args.summary:
            article_path = args.summary
            hackernews_manager.summary_writer.generate_article_summary(article_path, override=True)
        
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

            # check if markdown is for wechat public platform
            md_name_suffix = md_name.split('.')[-1] if '.' in md_name else ''
            is_wpp = md_name_suffix == 'wpp'
            
            renderer = MarkdownRenderer()
            html = renderer.generate_html_from_md_path(
                markdown_path=markdown_path,
                action='mistune',
                title='Geeknews',
                footer='2025. Geeknews',
                css_inline_flag=is_wpp,
                remove_h1=False,
                compact=is_wpp,
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
            final_title = story_title if story_title else 'HN热点汇总'

            email_notifier.dry_run = False
            email_notifier.notify(title=final_title, content=report_html, debug=args.test)

            LOG.info(f"[终端任务执行完毕] {report_path}") 

    def handle_email(self, args):
        email_notifier = self.geeknews_manager.email_notifier
        
        email_path = email_notifier.get_email_tester_path()
        if not os.path.exists(email_path):
            LOG.error(f"[终端任务]邮箱地址不存在: {email_path}")
            return

        if args.send:
            content_path = args.send
            if not os.path.exists(content_path) or os.path.isdir(content_path):
                LOG.error(f"[终端任务]无法发送邮件, 发送文件不存在{content_path}")
                return

            basename = os.path.basename(content_path)
            name, ext = os.path.splitext(basename)

            with open(content_path) as f:
                content = f.read()

            if ext == '.md':
                content = mistune.html(content)
            
            email_notifier.dry_run = args.dry_run
            email_notifier.notify(title=name, content=content, debug=args.test)
        
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
            wpp_notifier.post_draft()
        elif args.publish:
            wpp_notifier.publish_report()
        else:
            print('Not supported yet.')


def start_command_tool():
    manager = GeeknewsManager()
    handler = GeeknewsCommandHandler(manager)
    parser = handler.create_parser()
    args = parser.parse_args()
    args.func(args)