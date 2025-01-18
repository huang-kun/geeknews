import os, json
import mistune
from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.utils.md2html import MarkdownRenderer
from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager

LOCALIZED_TITLE = {
    'zh_cn': '极客号外',
    'en_us': 'Geeknews',
    'en': 'Geeknews',
}

class HackernewsReportWriter:
    '''Combine summaries and story-list into final report.'''

    def __init__(self, datapath_manager: HackernewsDataPathManager):
        self.datapath_manager = datapath_manager
        self.markdown_renderer = MarkdownRenderer()

    def generate_report(self, category='topstories', locale='zh_cn', date=GeeknewsDate.now(), override=False):
        '''Combine today's summaries to daily report.'''
        report_path = self.datapath_manager.get_report_file_path(locale, date)
        if not override and os.path.exists(report_path):
            return

        report_title = self.get_title(locale)
        report_contents = ['# ' + report_title, '']

        story_path = self.datapath_manager.get_stories_file_path(category, date)
        if not os.path.exists(story_path):
            LOG.error(f'无法生成报告, 未找到 {story_path}')
            return

        with open(story_path) as f:
            stories = json.load(f)

        for story in stories:
            article = story.get('article', False)
            if not article:
                continue
            story_id = story.get('id', 0)
            sum_path = self.datapath_manager.get_summary_file_path(story_id, locale, date)
            if not os.path.exists(sum_path):
                LOG.error(f'未找到生成的总结: {story_id}')
                continue
            with open(sum_path) as f:
                sum_content = f.read().strip()
                report_contents.append('###' + sum_content)
                report_contents.append('')

        sum_dir = self.datapath_manager.get_summary_full_dir(locale, date)
        short_story_path = os.path.join(sum_dir, 'short_stories.md')
        if os.path.exists(short_story_path):
            with open(short_story_path) as f:
                story_list_content = f.read()
                report_contents.append('#### ' + self.get_reference_title(locale))
                report_contents.append(story_list_content)

        if len(report_contents) <= 2:
            LOG.error(f'没有足够的信息生成报告')
            return

        final_report_content = '\n'.join(report_contents)
        with open(report_path, 'w') as f:
            f.write(final_report_content)

        # also make a html report
        html_title = LOCALIZED_TITLE.get(locale, 'Geeknews')
        html_footer = f'{date.year}. {html_title}'

        html_content = self.markdown_renderer.generate_html_from_md_path(
            markdown_path=report_path,
            action='mistune',
            title=html_title,
            footer=html_footer,
        )
        self.markdown_renderer.clean_all_caches()

        if not html_content:
            html_content = mistune.html(final_report_content)
        
        html_basename = os.path.basename(report_path)
        html_name, _ = os.path.splitext(html_basename)
        html_path = os.path.join(os.path.dirname(report_path), html_name + '.html')
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        LOG.debug(f"完成报告生成: {report_path}")

    def get_title(self, locale):
        if locale == 'zh_cn':
            return "Hacker News 今日热点"
        else:
            return "Hacker News Daily Stories"
        
    def get_reference_title(self, locale):
        if locale == 'zh_cn':
            return "其他热点摘要"
        else:
            return "Other topics"


def test_hackernews_report_writer():
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)
    writer = HackernewsReportWriter(dpm)
    writer.generate_report(category='topstories')