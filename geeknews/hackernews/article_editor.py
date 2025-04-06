import os
import json
import html
import re
import curl_cffi

from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

from geeknews.llm import LLM
from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate
from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.hackernews.api_client import HackernewsClient

"""
### [A minimax chess engine in regular expressions](https://nicholas.carlini.com/writing/2025/regex-chess.html)
{text}

**comments**:
- This is from the same gentleman who (among other things) demonstrated that printf() is Turing complete and wrote a first person shooter in 13kB of Javascript.
- This point was where this changed from crazy
- I fear not the man who plays chess with 84,688 regular expressions, but I fear the man who plays chess with one regular expression.
    - When I see this sort of thing I just I want to take my hat off and stand in solemn appreciation for the true heroes among men.
- This is not only a chess engine

REPLACE:
html.unescape(s)


<a href=...>...</a>
<p>
</p>

<i>
</i>

LLM:
- if has text, fill to {text}
- else read link and fill to {text}
    - read and summarize in 200 words
- if link is pdf and no text, remove {text}

"""


def count_words(text):
    return len(text.split())


def reduce_text_by_words(text, word_limit, truncated=False, placeholder='...(content omitted)...'):
    '''Reduce the text by limiting word count.'''
    word_count = count_words(text)
    extra_count = word_count - word_limit
    if extra_count <= 0:
        
        # insert placeholder in the middle if needed
        if truncated and placeholder:
            if '\n' in text and not '\n' in placeholder:
                placeholder = '\n\n' + placeholder + '\n\n'
            half_length = len(text) // 2
            return text[:half_length] + placeholder + text[half_length:]
        
        return text
    
    total_length = len(text)
    word_length = total_length // word_count
    extra_length = word_length * extra_count

    start_index = (total_length - extra_length) // 2
    end_index = start_index + extra_length
    
    # truncate text from middle section
    start_part = text[:start_index]
    end_part = text[end_index:]
    trunc_text = start_part + '..' + end_part

    return reduce_text_by_words(trunc_text, word_limit=word_limit, truncated=True, placeholder=placeholder)


class HackernewsSimpleStory:

    def __init__(self, id, title, url, text=None, comments=[], score=0, article=False):
        self.id = id
        self.title = title
        self.url = url
        self.text = text
        self.comments = comments
        self.score = score
        self.article = article  # should read link and comments 


class HackernewsSimpleComment:

    def __init__(self, text, comments=[]):
        self.text = text
        self.comments = comments


class HackernewsArticleEditor:
    '''Read link, generate article and comments from stories.json'''

    def __init__(self, llm: LLM, config: HackernewsConfig, datapath_manager: HackernewsDataPathManager):
        self.llm = llm
        self.config = config
        self.datapath_manager = datapath_manager
        self.link_re = re.compile(r'<a href=.*?\/a>')
        self.score_re = re.compile(r'-?\d+')
        self.job_title_re = re.compile(r'\(YC\s\w\d+\)\s\w+\s[Hh]iring')
        self.md_converter = MarkdownConverter()
    
    def parse_stories(self, stories):
        results = []
        for story in stories:
            story_text = self.parse_text(story.get('text', ''))
            story_comments = list(map(self.parse_comment, story.get('comments', []))) if self.config.summary_with_comments else []
            story_id = story.get('id', 0)
            simple_story = HackernewsSimpleStory(
                id=story_id,
                title=story.get('title', ''),
                url=story.get('url', HackernewsClient.get_default_story_url(story_id)),
                text=story_text,
                comments=story_comments,
                score=story.get('score', 0),
                article=story.get('article', False),
            )
            results.append(simple_story)
        return results

    def parse_text(self, text):
        if not isinstance(text, str) or not text:
            return ''
        
        text = self.link_re.sub('', text)
        text = html.unescape(text)
        
        replacements = {
            '<p>': ' ',
            '</p>': '',
            '<i>': '',
            '</i>': '',
            '\n': ' ',
        }

        for key, value in replacements.items():
            text = text.replace(key, value)

        return text
    
    def parse_comment(self, comment):
        if not isinstance(comment, dict) or not comment:
            return HackernewsSimpleComment('')
        if 'text' not in comment:
            return HackernewsSimpleComment('')
        
        text = self.parse_text(comment['text'])
        comments = []
        if 'comments' in comment:
            comments = list(map(self.parse_comment, comment['comments']))
        
        return HackernewsSimpleComment(text, comments)
    
    def generate_topstories_articles(self, date=GeeknewsDate.now()):
        self.generate_articles_for_category('topstories', date)
    
    def generate_articles_for_category(self, category, date=GeeknewsDate.now()):
        story_list_path = self.datapath_manager.get_stories_file_path(name=category, date=date)
        if not os.path.exists(story_list_path):
            LOG.debug(f'{category}路径不存在: {story_list_path}')
            return
        with open(story_list_path) as f:
            stories = json.load(f)
        self.generate_articles(stories, date)
        
    def generate_articles(self, stories, date=GeeknewsDate.now()):
        simple_stories = self.parse_stories(stories)
        LOG.debug(f'开始编辑')

        for story in simple_stories:
            article_path = self.datapath_manager.get_article_file_path(story.id, date)
            if os.path.exists(article_path):
                continue
            if not story.article:
                continue
            article = self.generate_article(story)
            if not article:
                LOG.debug(f'拒绝整理{story.id}, 没有内容')
                continue
            LOG.debug(f'完成全文编辑: {story.id}')
            with open(article_path, 'w') as f:
                f.write(article)

        LOG.debug(f'编辑结束: {self.datapath_manager.get_article_date_dir(date)}')
    
    def generate_article(self, story):
        if not self.support_story(story):
            return ''

        text = self.generate_article_text(story)
        if not text:
            return ''
        
        # check relevance of title and web content, maybe is empty web page.
        if text and not story.text:
            word_count = count_words(text)
            if word_count == 0:
                return ''
            if word_count < self.config.validate_word_count and self.llm:
                relevance_score = self.check_article_relevance_score(story.title, text)
                if relevance_score > self.config.validation_score:
                    LOG.info(f"{story.id} 文章内容相关性评分: {relevance_score}")
                else:
                    LOG.error(f"{story.id} 文章内容不相关: {relevance_score}")
                    return ''
        
        title = self.generate_article_title(story.title)
        comment = self.generate_article_comment(story.comments) if self.config.summary_with_comments else ''
        final_text = reduce_text_by_words(text, word_limit=self.config.max_word_count)
        
        if len(final_text) < len(text):
            LOG.info(f"{story.id} 文章词汇量有裁剪: 从{count_words(text)}减到{count_words(final_text)}")
        else:
            LOG.info(f"{story.id} 文章词汇量: {count_words(final_text)}")
        
        lines = []
        lines.append(title)
        lines.append(final_text)
        if comment:
            lines.append('')
            lines.append(comment)
        lines.append('')
        
        return '\n'.join(lines)
    
    def truncate_text_by_length(self, text, text_total_limit, text_head_limit):
        text_length = len(text)
        if text_length > text_total_limit:
            text_tail_limit = text_total_limit - text_head_limit
            head = text[:text_head_limit]
            tail = text[-text_tail_limit:]
            text = head + '\n\n...(content omitted)...\n\n' + tail
        
        return text
    
    def check_article_relevance_score(self, title, content):
        '''Check title and content relevance and return a score of 0-100.'''
        formatted_text = f"<title>{title}</title>\n<content>\n{content}\n</content>"
        result = self.llm.get_assistant_message(
            system_prompt=LLM.get_system_prompt('check_article_relevance', subdir='hackernews'),
            user_content=formatted_text,
        )
        if not result:
            return 0
        
        score_match = self.score_re.search(result)
        if not score_match:
            return 0
        
        score_text = score_match.group()
        try:
            score = int(score_text)
            return score
        except Exception as e:
            LOG.error(f"文章内容相关性评分解析失败: {e}")
            return 0

    def generate_article_title(self, title):
        return f"# {title}"
    
    def generate_article_text(self, story: HackernewsSimpleStory) -> str:
        text = self.get_markdown_text_from_url(story.url)
        if story.text:
            return story.text + '\n\n' + text
        return text
        
    def generate_article_comment(self, comments):
        if not comments:
            return ''
        lines = self.generate_article_comment_lines(comments)
        return 'USER_COMMENTS:\n' + '\n'.join(lines)
        
    def generate_article_comment_lines(self, comments, level=0):
        indent = ' ' * 4 * level
        lines = []

        for comment in comments:
            if not comment.text:
                continue
            
            line = indent + "- " + comment.text
            lines.append(line)

            if comment.comments:
                sub_comments = self.generate_article_comment_lines(comment.comments, level+1)
                lines.extend(sub_comments)
        
        return lines
    
    def get_markdown_text_from_url(self, url):
        if not url:
            return ''
        
        LOG.debug(f'正在读取链接: {url}')
        try:
            text = self.get_text_from_url_by_curl_impersonate(url)
            soup = BeautifulSoup(text, 'html.parser')
            return self.md_converter.convert_soup(soup)
        except Exception as e:
            LOG.error(str(e))
            return ''
    
    def get_text_from_url_by_urllib(self, url):
        # https://www.useragentstring.com/pages/Chrome/
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.5672 Safari/537.36'
        }

        # https://tariyekorogha.medium.com/solution-to-403-client-error-forbidden-for-url-with-python-3-180effbdb21
        try:
            request = Request(url, headers=headers)
            data = urlopen(request, timeout=30).read()
            return data.decode("utf-8")
        except Exception as e:
            LOG.error(str(e))
            return ''
        
    def get_text_from_url_by_curl_impersonate(self, url):
        # https://github.com/lexiforest/curl_cffi
        response = curl_cffi.get(url, impersonate="chrome")
        if response.status_code == 200:
            return response.text
        else:
            return ''
    
    def support_story(self, story: HackernewsSimpleStory):
        # if has text and not job hiring, then ok
        if story.text and not self.job_title_re.search(story.title):
            return True

        id = story.id
        url = story.url
        title = story.title.strip()

        if not url:
            LOG.error(f'{id} 无法读取链接, 空url')
            return False
        if url.endswith('.pdf') or url.startswith('https://arxiv.org/pdf/'):
            LOG.error(f'{id} 暂不支持pdf')
            return False
        if title.startswith('Ask HN:'):
            LOG.error(f'{id} 暂不支持Ask HN')
            return False
        if title.endswith('[video]'):
            LOG.error(f'{id} 暂不支持video')
            return False
        if self.job_title_re.search(title):
            LOG.error(f'{id} 暂不支持招聘信息')
            return False
        
        return True

    def download_article_content_by_story_path(self, story_path):
        '''For debugging!'''
        if not os.path.exists(story_path):
            return ''
        
        with open(story_path) as f:
            story = json.load(f)
        
        stories = self.parse_stories([story])
        return self.generate_article(stories[0])

def test_hackernews_article_editor():
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)    
    editor = HackernewsArticleEditor(None, config, dpm)
    editor.generate_topstories_articles()
    