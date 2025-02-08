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

    def publish_report(self, locale = 'zh_cn', date = GeeknewsDate.now(), thumb_media_id = None):
        # find report
        report_path = self.hackernews_manager.datapath_manager.get_report_file_path(locale=locale, date=date, ext='.wpp.html')
        if not report_path or not os.path.exists(report_path):
            LOG.error(f'公众号发布失败: 没有当日报告{date}')
            return
        
        # get report content
        story_title = self.hackernews_manager.get_daily_top_story_title(locale, date)
        final_title = f'HN热点: {story_title}' if story_title else 'Hacker News 热点汇总'
        
        with open(report_path) as f:
            report_content = f.read()

        # add draft
        article = WppDraftArticle(
            title=final_title,
            author=self.config.author_name,
            content=report_content,
            thumb_media_id=thumb_media_id if thumb_media_id else self.config.default_thumb_media_id
        )

        draft_result = self.api_client.add_draft(article)
        if 'media_id' in draft_result:
            media_id = draft_result['media_id']
            LOG.info(f'公众号发布成功: 草稿id - {media_id}')
        else:
            LOG.error(f'公众号发布失败: {json.dumps(draft_result)}')
