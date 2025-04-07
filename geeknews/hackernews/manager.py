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
        self.llm = llm
        self.config = config
        self.api_client = HackernewsClient(config, dpm)
        self.article_editor = HackernewsArticleEditor(llm, config, dpm)
        self.summary_writer = HackernewsSummaryWriter(llm, config, dpm)
        self.report_writer = HackernewsReportWriter(dpm)
        self.datapath_manager = dpm
    
    def generate_daily_report(self, locale='zh_cn', date=GeeknewsDate.now(), override=False):
        self.api_client.fetch_daily_stories(date)
        self.article_editor.generate_topstories_articles(date)
        self.summary_writer.generate_daily_summaries(locale, date, override)
        self.report_writer.generate_html_report('web', locale=locale, date=date, override=override)
        self.report_writer.generate_html_report('wpp', locale=locale, date=date, override=override)

    def get_daily_top_story_title_and_content(self, locale='zh_cn', date=GeeknewsDate.now(), limit=None):
        # find story id from topstories.json
        story_id = self.api_client.get_story_id_with_highest_score('topstories', article_only=True, date=date)
        if story_id <= 0:
            LOG.error('无法生成热点标题: 未能找到合适的数据')
            return '', ''
        
        # find title from summaries
        translated_title, summary = self.summary_writer.find_summary_title_and_content(story_id, locale, date, limit)
        if not translated_title:
            LOG.error(f'无法生成热点标题: {story_id}, {locale}, {date.joined_path}')
            return '', ''
        
        # if title has prefix like "Show HN: ", remove prefix to make title shorter
        modified_title = re.sub(r'^.*?HN:\s?', '', translated_title)
        modified_summary = summary
        if locale == 'zh_cn':
            end_char = '。'
            if not summary.endswith(end_char):
                try:
                    end_index = summary.rindex(end_char)
                    if end_index > 0:
                        modified_summary = summary[:end_index+1]
                except ValueError as e:
                    LOG.error(f'{e}')
                    modified_summary = summary
        
        return modified_title, modified_summary
    
    def generate_preview_json(self, date=GeeknewsDate.now(), locale='zh_cn'):
        _ = self.generate_preview_markdown(date, locale)
        return self.update_preview_json_with_translation(date, locale)

    def generate_preview_markdown(self, date=GeeknewsDate.now(), locale='zh_cn'):
        preview_path = self.api_client.generate_preview(date)
        
        self.summary_writer.generate_story_list_summary(
            story_list_path=preview_path,
            locale=locale,
            date=date,
            override=True,
            preview=True,
        )
        
        return self.get_preview_markdown_path(date, locale)
    
    def get_preview_markdown_path(self, date=GeeknewsDate.now(), locale='zh_cn'):
        preview_json_path = self.get_preview_json_path(date)
        summary_dir = self.datapath_manager.get_summary_full_dir(locale, date)
        preview_basename = os.path.basename(preview_json_path)
        preview_filename, _ = os.path.splitext(preview_basename)
        preview_md_path = os.path.join(summary_dir, f'{preview_filename}.md')
        return preview_md_path
    
    def get_preview_json_path(self, date=GeeknewsDate.now()):
        return self.api_client.get_preview_path(date)
    
    def update_preview_json_with_translation(self, date=GeeknewsDate.now(), locale='zh_cn'):
        '''update preview.json with translated title'''
        preview_json_path = self.get_preview_json_path(date)
        preview_md_path = self.get_preview_markdown_path(date, locale)
        
        with open(preview_json_path) as f:
            preview_objs = json.load(f)

        with open(preview_md_path) as f:
            preview_md = f.read()

        preview_news = preview_md.split("\n")
        regex_id = re.compile(r'\[\d+\]')
        translation = {}

        for item in preview_news:
            match_id = regex_id.search(item)
            if not match_id:
                continue
            id = match_id.group()[1:-1]
            text = item[match_id.end():].lstrip()
            translation[id] = text
        
        for item in preview_objs:
            id = item["id"]
            item["title"] = translation[str(id)]
        
        with open(preview_json_path, 'w') as f:
            json.dump(preview_objs, f, ensure_ascii=False)

        return preview_json_path

def test_hackernews_manager():
    llm = LLM()
    parser = GeeknewsConfigParser()
    config = HackernewsConfig.get_from_parser(parser)
    dpm = HackernewsDataPathManager(config)
    manager = HackernewsManager(llm, config, dpm)
    manager.generate_daily_report(override=True)
