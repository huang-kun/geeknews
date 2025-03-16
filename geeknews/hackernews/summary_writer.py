import os, re, json
from geeknews.llm import LLM
from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.api_client import HackernewsClient

TRANSLATION_VAR = '\{translate_target_language\}'
TRANSLATION_LOCALE_TO_LANGUAGE = {
    'zh_cn': 'Simplified Chinese',
    'en_us': 'English',
    'en': 'English',
}
TRANSLATION_COMMENT_TITLE = {
    'zh_cn': '读者评论',
    'en_us': 'User commments',
    'en': 'User comments',
}

class HackernewsSummaryWriter:
    '''
    Summarize article and comments, then generate a short description.
    Also translate story list.
    '''

    def __init__(self, llm: LLM, config: HackernewsConfig, datapath_manager: HackernewsDataPathManager):
        self.llm = llm
        self.config = config
        self.datapath_manager = datapath_manager
        self.prompt_map = LLM.get_system_prompt_map(subdir='hackernews')
        self.re_trans_var = re.compile(TRANSLATION_VAR)
        self.re_title = re.compile(r'^(#{1,6})\s*(?P<head>.+)\n*')
        self.re_comment_tag = re.compile(r'USER_COMMENTS:\s*\n*')

    def generate_daily_summaries(self, locale='zh_cn', date=GeeknewsDate.now(), override=False):
        article_paths = self.datapath_manager.get_daily_article_paths(date)
        story_date_dir = self.datapath_manager.get_story_date_dir(date)
        short_story_path = os.path.join(story_date_dir, 'short_stories.json')

        LOG.debug(f'开始总结以下文章, 数量: {len(article_paths)}')

        for article_path in article_paths:
            self.generate_article_summary(article_path, locale, date, override)
        self.generate_story_list_summary(short_story_path, locale, date, override)

        LOG.debug(f'总结完成: {self.datapath_manager.get_summary_full_dir(locale, date)}')

    def generate_article_summary(self, article_path, locale='zh_cn', date=GeeknewsDate.now(), override=False):
        article_filename = os.path.basename(article_path)
        article_id, _ = os.path.splitext(article_filename)
        
        # Get story (with url, author, score)
        story = {}
        story_path = self.datapath_manager.get_story_file_path(article_id, date)
        if os.path.exists(story_path):
            with open(story_path) as f:
                story = json.load(f)
        
        summary_path = self.datapath_manager.get_summary_file_path(article_id, locale, date)
        if not override and os.path.exists(summary_path):
            return

        with open(article_path) as f:
            article_content = f.read().strip()
        
        language = self.get_translation_language(locale)
        if language == 'English':
            system_prompt = self.prompt_map['summary_article_en']
        else:
            system_prompt = self.re_trans_var.sub(language, self.prompt_map['summary_article'])

        LOG.debug(f'开始总结文章: {article_id}')
        summary_content = self.llm.generate_text(system_prompt, article_content, self.config.summary_model)
        final_content = self.modify_summarized_content(
            article_id=article_id, 
            article_url=story.get('url', HackernewsClient.get_default_story_url(article_id)), 
            content=summary_content, 
            locale=locale
        )
        
        with open(summary_path, 'w') as f:
            f.write(final_content)

    def generate_story_list_summary(self, story_list_path, locale='zh_cn', date=GeeknewsDate.now(), override=False):
        if not os.path.exists(story_list_path):
            return
        
        story_list_filename = os.path.basename(story_list_path)
        story_list_ori_name, _ = os.path.splitext(story_list_filename)
        summary_full_dir = self.datapath_manager.get_summary_full_dir(locale, date)
        summary_list_path = os.path.join(summary_full_dir, story_list_ori_name + '.md')
        
        if not override and os.path.exists(summary_list_path):
            return
        
        with open(story_list_path) as f:
            short_stories = json.load(f)
        
        if not short_stories:
            return

        language = self.get_translation_language(locale)
        
        # no need to translate English
        if language != 'English':
            system_prompt = re.sub(TRANSLATION_VAR, language, self.prompt_map['translate_story_list'])
            
            bullet_mark = '- '
            story_titles = []
            for story in short_stories:
                title = story['title'].replace('\n', '')
                story_titles.append(bullet_mark + title)

            LOG.debug('开始翻译故事列表')
            translated_content = self.llm.get_assistant_message(system_prompt, '\n'.join(story_titles))
            if not translated_content:
                return
            
            translated_titles = translated_content.split('\n')
            if len(story_titles) != len(translated_titles):
                LOG.error(f"大模型翻译故事列表出错, 前后列表数量不一致: {len(story_titles)} != {len(translated_titles)}")
                # save content for debugging
                summary_list_trans_path = os.path.join(summary_full_dir, story_list_ori_name + '_trans.md')
                with open(summary_list_trans_path, 'w') as f:
                    f.write(translated_content)
                return
            
            for index, story in enumerate(short_stories):
                translated_title = translated_titles[index]
                story['title'] = translated_title[2:] if translated_title.startswith(bullet_mark) else translated_title

        summary_contents = list(map(lambda s: f"{bullet_mark}{s['title']} [>>]({s['url']})", short_stories))
        with open(summary_list_path, 'w') as f:
            f.write('\n'.join(summary_contents))

    def find_summary_title(self, story_id, locale='zh_cn', date=GeeknewsDate.now()):
        summary_path = self.datapath_manager.get_summary_file_path(story_id, locale, date)
        if not os.path.exists(summary_path):
            return ''
        
        with open(summary_path) as f:
            first_line = f.readline().strip()

        if not first_line.startswith('# '):
            return ''
        
        return first_line[2:].strip()

    def get_translation_language(self, locale):
        return TRANSLATION_LOCALE_TO_LANGUAGE.get(locale, 'English')
    
    def modify_summarized_content(self, article_id, article_url, content, locale='zh_cn'):
        # search title
        title_match = self.re_title.search(content)
        if title_match:
            # remove extra \n after title
            title_format = title_match.group()
            title_end = title_match.end()
            title = title_format.rstrip()
            content = title + '\n' + content[title_end:]
        
        # search comment
        comment_match = self.re_comment_tag.search(content)
        if comment_match:
            # add article link to the end of article content
            comment_start = comment_match.start()
            article_last_char_index = self.find_text_ended_before_index(content, comment_start)
            if article_last_char_index > 0:
                article_link = f'[>>]({article_url})'
                content = self.insert_str(content, article_link, article_last_char_index+1)

            # add comment link to the end of comments
            comment_url = f'https://news.ycombinator.com/item?id={article_id}'
            comment_link = f'[>>]({comment_url})'
            if content.endswith('\n'):
                content_last_char_index = self.find_text_ended_before_index(content, len(content)-1)
                if content_last_char_index > 0:
                    content = self.insert_str(content, comment_link, content_last_char_index+1)
            else:
                content = content + comment_link

            # replace comment tag
            comment_title = TRANSLATION_COMMENT_TITLE.get(locale, 'User comments') + ': '
            content = self.re_comment_tag.sub(comment_title, content)
            # replace no comment tag
            if 'NO_COMMENT' in content:
                content = content.replace('NO_COMMENT', '', 1)
            
        else:
            # add article link to end of content
            article_link = f'[>>]({article_url})'
            if content.endswith('\n'):
                content_last_char_index = self.find_text_ended_before_index(content, len(content)-1)
                if content_last_char_index > 0:
                    content = self.insert_str(content, article_link, content_last_char_index+1)
            else:
                content = content + article_link

        return content
    
    @staticmethod
    def insert_str(base_string, insert_string, index):
        '''Inserts a string into another string at a specified index.'''
        if index < 0:
            index = 0
        return base_string[:index] + insert_string + base_string[index:]

    @staticmethod
    def find_text_ended_before_index(base_string, before_index):
        if before_index < 1 or base_string[before_index-1] != '\n':
            return -1
        for i in range(before_index-1, 0, -1):
            if base_string[i] == '\n':
                continue
            return i


def test_hackernews_summary_writer():
    llm = LLM()
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)
    writer = HackernewsSummaryWriter(llm, config, dpm)
    writer.generate_daily_summaries()