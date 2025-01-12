import os
import requests
import json
from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.utils.logger import LOG

# https://github.com/HackerNews/API

class HackernewsApi:    

    def __init__(self):
        self.base_url = 'https://hacker-news.firebaseio.com/v0'

    def top_stories_url(self):
        '''hacker news main page top stories'''
        return self.get_stories_url('topstories')
    
    def new_stories_url(self):
        return self.get_stories_url('newstories')
    
    def best_stories_url(self):
        return self.get_stories_url('beststories')
    
    def ask_stories_url(self):
        return self.get_stories_url('askstories')
    
    def show_stories_url(self):
        return self.get_stories_url('showstories')
    
    def job_stories_url(self):
        return self.get_stories_url('jobstories')
    
    def get_item_url(self, id):
        return f"{self.base_url}/item/{id}.json"
    
    def get_stories_url(self, api):
        return f"{self.base_url}/{api}.json"


class HackernewsClient:

    def __init__(self, config: HackernewsConfig, datapath_manager: HackernewsDataPathManager):
        self.api = HackernewsApi()
        self.config = config
        self.datapath_manager = datapath_manager

    def http_get(self, url, empty_data=[]):
        response = requests.get(url)
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            LOG.error(str(err))
            return empty_data
        
    def fetch_item(self, id):
        url = self.api.get_item_url(id)
        return self.http_get(url, empty_data={})
        
    def get_item(self, id, item_type='story', parent_id=None, recursive=False, remain_comment_count=10, current_num=0, mark_article=False):
        item = self.get_local_item(id)
        
        if not item:
            action_log = '开始下载'
            item = self.fetch_item(id)
            self.save_item(id, item)
        else:
            action_log = '本地读取'

        parent_log = f'源自{parent_id}, ' if parent_id else ''
        article_log = f'精读文章' if mark_article else ''
        LOG.debug(f'{action_log}{item_type}: {id}, {parent_log}当前是第{current_num}个, {article_log}')

        if mark_article:
            item['article'] = True
        if not recursive:
            return item
        if 'kids' not in item:
            return item
        
        comment_ids = item['kids']
        real_comment_count = len(comment_ids)
        LOG.debug(f'获取{id}的评论剩余数量: {remain_comment_count}, 实际评论数量: {real_comment_count}')
        
        if remain_comment_count <= 0:
            comment_ids = []
        elif remain_comment_count < real_comment_count:
            comment_ids = comment_ids[:remain_comment_count]
            remain_comment_count = 0
        elif remain_comment_count > real_comment_count:
            remain_comment_count -= real_comment_count
        elif remain_comment_count == real_comment_count:
            remain_comment_count = 0
        
        comments = []
        for index, comment_id in enumerate(comment_ids):
            comment = self.get_item(
                id=comment_id,
                item_type='comment',
                parent_id=id,
                recursive=True,
                remain_comment_count=remain_comment_count,
                current_num=index+1,
                mark_article=False,
            )
            comments.append(comment)

        del item['kids']
        if comments:
            item['comments'] = comments
        
        return item
    
    def fetch_daily_stories(self):
        # fetch and save top stories json
        stories = self.fetch_top_stories()
        stories_file_path = self.datapath_manager.get_stories_file_path(name='topstories')
        with open(stories_file_path, 'w') as f:
            json.dump(stories, f, ensure_ascii=False, indent=4)

        # filter stories which are not marked as articles, and save to json list
        short_stories = []
        for story in stories:
            article = story.get('article', False)
            if not article and 'id' in story and 'title' in story and 'url' in story:
                short_stories.append({
                    'id': story['id'],
                    'by': story.get('by', ''),
                    'title': story['title'],
                    'url': story['url'],
                    'score': story.get('score', 0),
                    'time': story.get('time', 0),
                    'comment_count': len(story['kids']) if 'kids' in story else 0,
                })

        story_date_dir = os.path.dirname(stories_file_path)
        if short_stories:
            short_stories_path = os.path.join(story_date_dir, 'short_stories.json')
            with open(short_stories_path, 'w') as f:
                json.dump(short_stories, f, ensure_ascii=False, indent=4)
        
        LOG.debug(f'完成获取stories: {story_date_dir}')

    def fetch_top_stories(self):
        story_limit = self.config.daily_story_max_count
        comment_limit = self.config.each_story_max_comment_count
        article_limit = self.config.daily_article_max_count

        LOG.debug(f'开始请求top stories')
        story_ids = self.http_get(self.api.top_stories_url(), empty_data=[])
        LOG.debug(f'已请求top stories id数量共{len(story_ids)}个, 限制下载{story_limit}个')

        sub_ids = story_ids[:story_limit]
        items = []
        for index, id in enumerate(sub_ids):
            current_num = index + 1
            # the top n stories will be generate to articles (which mark_article=True),
            # others will just remain title and link (which mark_article=False).
            mark_article = current_num <= article_limit
            item = self.get_item(
                id=id,
                item_type='story',
                parent_id=None,
                recursive=mark_article,
                remain_comment_count=comment_limit if mark_article else 0,
                current_num=current_num,
                mark_article=mark_article,
            )
            items.append(item)
        return items
    
    def get_local_item(self, id):
        story_path = self.get_story_path(id)
        if os.path.exists(story_path):
            with open(story_path) as f:
                return json.load(f)
        return {}
    
    def save_item(self, id, item):
        story_path = self.get_story_path(id)
        story_dir = os.path.dirname(story_path)
        if not os.path.exists(story_dir):
            os.makedirs(story_dir)
        with open(story_path, 'w') as f:
            json.dump(item, f, ensure_ascii=False)

    def get_story_path(self, id):
        return self.datapath_manager.get_story_file_path(id)


def test_hackernews_client():
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)
    client = HackernewsClient(config=config, datapath_manager=dpm)
    client.fetch_daily_stories()
