import os, re, json
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
        self.embeded_urls = []
        self.re_link = re.compile(r'\[>>\]\((?P<url>.*?)\)')

    def generate_html_report(
            self,
            report_type,
            locale='zh_cn', 
            date=GeeknewsDate.now(), 
            override=False, 
        ):
        if report_type == 'web':
            self.generate_report(
                'topstories', 
                locale=locale, 
                date=date, 
                override=override, 
                extract_links=False
            )
        elif report_type == 'wpp':
            self.generate_report(
                'topstories', 
                locale=locale, 
                date=date, 
                override=override, 
                extract_links=True, 
                md_suffix_name='.wpp', 
                html_suffix_name='.wpp', 
                css_inline=True,
                remove_h1=False,
                compact=True, # 微信公众号需要在网页里去除换行符，否则会在草稿编辑器里生成多余的br标签
            )

    def generate_report(
            self, 
            category='topstories', 
            locale='zh_cn', 
            date=GeeknewsDate.now(), 
            override=False, 
            extract_links=False, 
            md_suffix_name = '',
            html_suffix_name='',
            css_inline=False,
            remove_h1=False,
            compact=False,
        ):
        '''
        Combine today's summaries to daily report.
        If extrack_links=True, then extract embeded links to bottom.
        '''
        report_path = self.datapath_manager.get_report_file_path(locale=locale, date=date, ext=md_suffix_name+'.md')
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
                if extract_links:
                    sum_content = self.re_link.sub(self.get_link_number, sum_content)
                report_contents.append('###' + sum_content)
                report_contents.append('')

        sum_dir = self.datapath_manager.get_summary_full_dir(locale, date)
        short_story_path = os.path.join(sum_dir, 'short_stories.md')
        if os.path.exists(short_story_path):
            with open(short_story_path) as f:
                story_list_content = f.read()
                if extract_links:
                    story_list_content = self.re_link.sub(self.get_link_number, story_list_content)
                report_contents.append('#### ' + self.get_other_topics_title(locale))
                report_contents.append(story_list_content)
                report_contents.append('')

        if len(report_contents) <= 2:
            LOG.error(f'没有足够的信息生成报告')
            return
        
        # Put reference section to the bottom and list urls
        reference_contents = []
        if extract_links and self.embeded_urls:
            reference_contents.append('#### ' + self.get_reference_title(locale))
            for i, url in enumerate(self.embeded_urls):
                reference_contents.append(f'{i+1}. {url}')
        if reference_contents:
            report_contents.extend(reference_contents)

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
            css_inline_flag=css_inline,
            remove_h1=remove_h1,
            compact=compact,
        )
        self.markdown_renderer.clean_all_caches()

        if not html_content:
            html_content = mistune.html(final_report_content)
        
        html_basename = os.path.basename(report_path)
        html_name, _ = os.path.splitext(html_basename)
        if html_suffix_name and not html_name.endswith(html_suffix_name):
            html_name += html_suffix_name
        html_path = os.path.join(os.path.dirname(report_path), html_name + '.html')
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        if self.embeded_urls:
            self.embeded_urls = []
        
        LOG.debug(f"完成报告生成: {report_path}")

    def get_title(self, locale):
        if locale == 'zh_cn':
            return "HN今日热点"
        else:
            return "HN: Daily Stories"
        
    def get_other_topics_title(self, locale):
        if locale == 'zh_cn':
            return "其他热点摘要"
        else:
            return "Other topics"
        
    def get_reference_title(self, locale):
        if locale == 'zh_cn':
            return "引用来源"
        else:
            return "Reference"
                
    def get_link_number(self, link_match):
        url = link_match.group('url')
        self.embeded_urls.append(url)
        link_num = len(self.embeded_urls)
        return f'[^{link_num}]'

def test_hackernews_report_writer():
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)
    writer = HackernewsReportWriter(dpm)
    writer.generate_report(category='topstories')