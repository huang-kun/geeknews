from geeknews.configparser import GeeknewsConfigParser

class HackernewsConfig:

    section = 'Hackernews'

    story_dir: str
    article_dir: str
    summary_dir: str
    report_dir: str

    daily_story_max_count: int
    daily_article_max_count: int
    each_story_max_comment_count: int

    max_word_count: int

    update_freq_days: int
    update_exec_time: str
    exec_time_zone: str

    @classmethod
    def get_from_parser(cls, configparser: GeeknewsConfigParser = GeeknewsConfigParser()):
        cls.story_dir = configparser.get_abs_path(cls.section, 'story_dir')
        cls.article_dir = configparser.get_abs_path(cls.section, 'article_dir')
        cls.summary_dir = configparser.get_abs_path(cls.section, 'summary_dir')
        cls.report_dir = configparser.get_abs_path(cls.section, 'report_dir')

        cls.daily_story_max_count = configparser.get_integer(cls.section, 'daily_story_max_count')
        cls.daily_article_max_count = configparser.get_integer(cls.section, 'daily_article_max_count')
        cls.each_story_max_comment_count = configparser.get_integer(cls.section, 'each_story_max_comment_count')

        cls.max_word_count = configparser.get_integer(cls.section, 'max_word_count')

        cls.update_freq_days = configparser.get_integer(cls.section, 'update_freq_days')
        cls.update_exec_time = configparser.get(cls.section, 'update_exec_time')
        cls.exec_time_zone = configparser.get(cls.section, 'exec_time_zone')

        return cls()