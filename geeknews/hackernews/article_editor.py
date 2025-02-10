import os
import json
import html
import re
import requests
import html2text
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

    def __init__(self, config: HackernewsConfig, datapath_manager: HackernewsDataPathManager):
        self.config = config
        self.datapath_manager = datapath_manager
        self.link_re = re.compile(r'<a href=.*?\/a>')
    
    def parse_stories(self, stories):
        results = []
        for story in stories:
            story_text = self.parse_text(story.get('text', ''))
            story_comments = list(map(self.parse_comment, story.get('comments', [])))
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
        text = self.generate_article_text(story)
        if not text:
            return ''
        
        title = self.generate_article_title(story.title)
        comment = self.generate_article_comment(story.comments)

        text_total_limit = self.config.article_text_max_length
        text_head_limit = self.config.article_text_head_length

        text_length = len(text)
        if text_length > text_total_limit:
            text_tail_limit = text_total_limit - text_head_limit
            head = text[:text_head_limit]
            tail = text[-text_tail_limit:]
            text = head + '\n\n...(content omitted)...\n\n' + tail

        lines = []
        lines.append(title)
        lines.append(text)
        if comment:
            lines.append('')
            lines.append(comment)
        lines.append('')
        
        return '\n'.join(lines)

    def generate_article_title(self, title):
        return f"# {title}"
    
    def generate_article_text(self, story: HackernewsSimpleStory) -> str:
        if story.text:
            return story.text
        else:
            return self.read_text_from_url(story.url)
        
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
    
    def read_text_from_url(self, url):
        if not url:
            LOG.error(f'无法读取链接, 空url')
            return ''
        if url.endswith('.pdf'):
            LOG.error(f'无法读取链接, 暂不支持pdf')
            return ''
        
        LOG.debug(f'正在读取链接: {url}')
        try:
            response = requests.get(url)
            response.raise_for_status()

            if "text/html" in response.headers.get("Content-Type", "") or response.text.startswith("<!DOCTYPE html>"):
                text_maker = html2text.HTML2Text()
                text_maker.ignore_links = True
                text_maker.bypass_tables = False
                text = text_maker.handle(response.text)
                return text.strip()
            else:
                LOG.error(f'从网页中提取文本失败: {url}')
                return ''
        except Exception as e:
            LOG.error(str(e))
            return ''


def test_hackernews_article_editor():
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)    
    editor = HackernewsArticleEditor(config, dpm)
    editor.generate_topstories_articles()
    