# Wechat Public Platform
import os
import json
import requests
from datetime import datetime, timedelta
from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.config import GeeknewsWechatPPConfig
from geeknews.notifier.wechatpp.client.client import WppClient
from geeknews.notifier.wechatpp.api.draft import WppDraftArticle
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.manager import HackernewsManager


class WppNotifier:

    def __init__(self, config: GeeknewsWechatPPConfig, hackernews_manager: HackernewsManager):
        self.config = config
        self.api_client = WppClient(config)
        self.hackernews_manager = hackernews_manager

    def post_draft(self, locale = 'zh_cn', date = GeeknewsDate.now(), thumb_media_id = None):
        # find report
        report_path = self.hackernews_manager.datapath_manager.get_report_file_path(locale=locale, date=date, ext='.wpp.html')
        if not report_path or not os.path.exists(report_path):
            LOG.error(f'公众号发布失败: 没有当日报告{date}')
            return
        
        # get report content
        story_title = self.hackernews_manager.get_daily_top_story_title(locale, date)
        final_title = f'HN热点: {story_title}' if story_title else 'HN热点汇总'
        
        with open(report_path) as f:
            report_content = f.read()

        # add draft
        article = WppDraftArticle(
            title=final_title,
            author=self.config.author_name,
            content=report_content,
            thumb_media_id=thumb_media_id if thumb_media_id else self.config.default_media_id
        )

        draft_result = self.api_client.add_draft(article)
        draft_id = draft_result.get('media_id', '')
        if draft_id:
            report_dir = os.path.dirname(report_path)
            draft_id_path = os.path.join(report_dir, 'wpp_draft_id.txt')
            with open(draft_id_path, 'w') as f:
                f.write(draft_id)
            LOG.info(f'公众号发布草稿成功: id - {draft_id}')
        else:
            LOG.error(f'公众号发布草稿失败: {json.dumps(draft_result)}')

    def publish_report(self, locale = 'zh_cn', date = GeeknewsDate.now()):
        report_path = self.hackernews_manager.datapath_manager.get_report_file_path(locale=locale, date=date, ext='.wpp.html')
        report_dir = os.path.dirname(report_path)
        draft_id_path = os.path.join(report_dir, 'wpp_draft_id.txt')

        if not os.path.exists(draft_id_path):
            LOG.error(f'公众号发布失败: 没有草稿信息{date}')
            return
        
        with open(draft_id_path) as f:
            draft_id = f.read().strip()
        
        result = self.api_client.publish(draft_id)
        if 'errcode' in result and result['errcode'] != 0:
            LOG.error(f'公众号发布失败: {json.dumps(result)}')
        else:
            LOG.info(f'公众号发布成功, 等待审核: {json.dumps(result)}')