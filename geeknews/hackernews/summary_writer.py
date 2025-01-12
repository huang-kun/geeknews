import os, re, json
from geeknews.llm import LLM
from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager

TRANSLATION_VAR = '\{translate_target_language\}'
TRANSLATION_LOCALE_TO_LANGUAGE = {
    'zh_cn': 'Mandarin',
    'en_us': 'English',
    'en': 'English',
}

class HackernewsSummaryWriter:
    '''
    Summarize article and comments, then generate a short description.
    Also translate story list.
    '''

    def __init__(self, llm: LLM, datapath_manager: HackernewsDataPathManager):
        self.llm = llm
        self.datapath_manager = datapath_manager
        self.prompt_map = self.load_prompts()
        self.re_trans_var = re.compile(TRANSLATION_VAR)
        self.re_comment_url_tag = re.compile('COMMENT_URL_TAG')

    @staticmethod
    def load_prompts():
        prompts_dir = os.path.join('prompts', 'hackernews')

        prompt_map = {}
        for filename in os.listdir(prompts_dir):
            basename, ext = os.path.splitext(filename)
            if ext != '.txt':
                continue
            prompt_path = os.path.join(prompts_dir, filename)
            with open(prompt_path) as f:
                prompt_map[basename] = f.read().strip()
        
        return prompt_map

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
        summary_content = self.llm.get_assistant_message(system_prompt, article_content)
        comment_url = f'https://news.ycombinator.com/item?id={article_id}'
        final_content = self.re_comment_url_tag.sub(comment_url, summary_content, count=1)
        
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
                return
            
            for index, story in enumerate(short_stories):
                translated_title = translated_titles[index]
                story['title'] = translated_title[2:] if translated_title.startswith(bullet_mark) else translated_title

        summary_contents = list(map(lambda s: f"{bullet_mark}[{s['title']}]({s['url']})", short_stories))
        with open(summary_list_path, 'w') as f:
            f.write('\n'.join(summary_contents))

    def get_translation_language(self, locale):
        return TRANSLATION_LOCALE_TO_LANGUAGE.get(locale, 'English')


def test_hackernews_summary_writer():
    llm = LLM()
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)
    writer = HackernewsSummaryWriter(llm, dpm)
    writer.generate_daily_summaries()