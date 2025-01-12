from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate

from geeknews.llm import LLM
from geeknews.notifier.email_notifier import GeeknewsEmailNotifier
from geeknews.configparser import GeeknewsConfigParser
from geeknews.config import GeeknewsEmailConfig

from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.manager import HackernewsManager


class GeeknewsManager:

    def __init__(self):
        llm = LLM()

        configparser = GeeknewsConfigParser()
        hackernews_config = HackernewsConfig.get_from_parser(configparser)
        hackernews_dpm = HackernewsDataPathManager(hackernews_config)
        
        hackernews_manager = HackernewsManager(llm, hackernews_config, hackernews_dpm)

        email_config = GeeknewsEmailConfig.get_from_parser(configparser)
        email_notifier = GeeknewsEmailNotifier(email_config)

        self.llm = llm
        self.configparser = configparser

        self.hackernews_config = hackernews_config
        self.hackernews_dpm = hackernews_dpm
        self.hackernews_manager = hackernews_manager
        
        self.email_config = email_config
        self.email_notifier = email_notifier