import os
from geeknews.utils.date import GeeknewsDate
from geeknews.hackernews.config import HackernewsConfig


def auto_make_dirs(func):
    def wrapper(*args, **kwargs):
        dir = func(*args, **kwargs)
        if not os.path.exists(dir):
            os.makedirs(dir)
        return dir
    return wrapper


class HackernewsDataPathManager:

    def __init__(self, config: HackernewsConfig):
        self.config = config
        self.enable_debug_date = False
    
    @auto_make_dirs
    def get_story_date_dir(self, date=GeeknewsDate.now()):
        if date is None:
            return self.config.story_dir
        else:
            return self._get_dir_with_date(self.config.story_dir, date)

    def get_story_file_path(self, id, date=GeeknewsDate.now()):
        story_date_dir = self.get_story_date_dir(date)
        return os.path.join(story_date_dir, f'{id}.json')
        
    def get_stories_file_path(self, name='topstories', date=GeeknewsDate.now()):
        story_date_dir = self._get_dir_with_date(self.config.story_dir, date)
        return os.path.join(story_date_dir, f'{name}.json')
    
    @auto_make_dirs
    def get_article_date_dir(self, date=GeeknewsDate.now()):
        if date is None:
            return self.config.article_dir
        else:
            return self._get_dir_with_date(self.config.article_dir, date)
        
    def get_article_file_path(self, id, date=GeeknewsDate.now()):
        article_date_dir = self.get_article_date_dir(date)
        return os.path.join(article_date_dir, f'{id}.md')
    
    def get_daily_article_paths(self, date=GeeknewsDate.now()):
        article_date_dir = self.get_article_date_dir(date)
        filenames = os.listdir(article_date_dir)
        paths = []
        for filename in filenames:
            if not filename.endswith('.md'):
                continue
            file_path = os.path.join(article_date_dir, filename)
            paths.append(file_path)
        return paths
    
    @auto_make_dirs
    def get_summary_full_dir(self, locale='zh_cn', date=GeeknewsDate.now()):
        if locale is None and date is None:
            return self.config.summary_dir
        else:
            return self._get_full_dir(self.config.summary_dir, locale, date)
        
    def get_summary_file_path(self, id, locale='zh_cn', date=GeeknewsDate.now()):
        summary_full_dir = self.get_summary_full_dir(locale, date)
        return os.path.join(summary_full_dir, f'{id}.md')
    
    def get_daily_summary_paths(self, locale='zh_cn', date=GeeknewsDate.now()):
        summary_full_dir = self.get_summary_full_dir(locale, date)
        filenames_iter = filter(lambda x: x.endswith('.md'), os.listdir(summary_full_dir))
        return list(map(lambda x: os.path.join(summary_full_dir, x), filenames_iter))
    
    @auto_make_dirs
    def get_report_full_dir(self, locale='zh_cn', date=GeeknewsDate.now()):
        if locale is None:
            return self.config.report_dir
        else:
            final_date = self._get_date(date)
            result_dir = os.path.join(self.config.report_dir, locale, final_date.joined_path)
            return os.path.dirname(result_dir) # remove last path, e.g. 2025/1/9/ -> 2025/1/
        
    def get_report_file_path(self, locale='zh_cn', date=GeeknewsDate.now(), ext='.md'):
        report_full_dir = self.get_report_full_dir(locale, date)
        final_date = self._get_date(date)
        return os.path.join(report_full_dir, f'{final_date.formatted}{ext}')

    def _get_dir_with_date(self, dir: str, date: GeeknewsDate) -> str:
        final_date = self._get_date(date)
        return os.path.join(dir, final_date.joined_path)
    
    def _get_full_dir(self, dir: str, locale: str, date: GeeknewsDate) -> str:
        final_date = self._get_date(date)
        return os.path.join(dir, locale, final_date.joined_path)

    def _get_date(self, date: GeeknewsDate) -> GeeknewsDate:
        return date if not self.enable_debug_date else GeeknewsDate.test_date()

    