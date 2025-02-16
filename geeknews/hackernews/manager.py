import os
import re
import json

from geeknews.configparser import GeeknewsConfigParser
from geeknews.llm import LLM

from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.utils.md2html import MarkdownRenderer

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.api_client import HackernewsClient
from geeknews.hackernews.article_editor import HackernewsArticleEditor
from geeknews.hackernews.summary_writer import HackernewsSummaryWriter
from geeknews.hackernews.report_writer import HackernewsReportWriter

class HackernewsManager:

    def __init__(self, llm: LLM, config: HackernewsConfig, dpm: HackernewsDataPathManager):        
        self.api_client = HackernewsClient(config, dpm)
        self.article_editor = HackernewsArticleEditor(llm, config, dpm)
        self.summary_writer = HackernewsSummaryWriter(llm, dpm)
        self.report_writer = HackernewsReportWriter(dpm)
        self.datapath_manager = dpm
    
    def generate_daily_report(self, locale='zh_cn', date=GeeknewsDate.now(), override=False):
        self.api_client.fetch_daily_stories(date)
        self.article_editor.generate_topstories_articles(date)
        self.summary_writer.generate_daily_summaries(locale, date, override)
        self.report_writer.generate_html_report('web', locale=locale, date=date, override=override)
        self.report_writer.generate_html_report('wpp', locale=locale, date=date, override=override)

    def get_daily_top_story_title(self, locale='zh_cn', date=GeeknewsDate.now()):
        # find story id from topstories.json
        story_id = self.api_client.get_story_id_with_highest_score('topstories', article_only=True, date=date)
        if story_id <= 0:
            LOG.error('无法生成热点标题: 未能找到合适的数据')
            return ''
        
        # find title from summaries
        translated_title = self.summary_writer.find_summary_title(story_id, locale, date)
        if not translated_title:
            LOG.error(f'无法生成热点标题: {story_id}, {locale}, {date.joined_path}')
            return ''
        
        # if title has prefix like "Show HN: ", remove prefix to make title shorter
        return re.sub(r'^.*?HN:\s?', '', translated_title)

def test_hackernews_manager():
    llm = LLM()
    parser = GeeknewsConfigParser()
    config = HackernewsConfig.get_from_parser(parser)
    dpm = HackernewsDataPathManager(config)
    manager = HackernewsManager(llm, config, dpm)
    manager.generate_daily_report(override=True)