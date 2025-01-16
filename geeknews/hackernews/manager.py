from geeknews.configparser import GeeknewsConfigParser
from geeknews.llm import LLM

from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.api_client import HackernewsClient
from geeknews.hackernews.article_editor import HackernewsArticleEditor
from geeknews.hackernews.summary_writer import HackernewsSummaryWriter
from geeknews.hackernews.report_writer import HackernewsReportWriter

class HackernewsManager:

    def __init__(self, llm: LLM, config: HackernewsConfig, dpm: HackernewsDataPathManager):        
        self.api_client = HackernewsClient(config, dpm)
        self.article_editor = HackernewsArticleEditor(config, dpm)
        self.summary_writer = HackernewsSummaryWriter(llm, dpm)
        self.report_writer = HackernewsReportWriter(dpm)
    
    def generate_daily_report(self, locale='zh_cn', date=GeeknewsDate.now(), override=False):
        self.api_client.fetch_daily_stories(date)
        self.article_editor.generate_topstories_articles(date)
        self.summary_writer.generate_daily_summaries(locale, date, override)
        self.report_writer.generate_report('topstories', locale, date, override)


def test_hackernews_manager():
    llm = LLM()
    parser = GeeknewsConfigParser()
    config = HackernewsConfig.get_from_parser(parser)
    dpm = HackernewsDataPathManager(config)
    manager = HackernewsManager(llm, config, dpm)
    manager.generate_daily_report(override=True)