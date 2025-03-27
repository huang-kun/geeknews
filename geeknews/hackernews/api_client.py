import os
import re
import requests
import json
import aiohttp
import aiofiles
import asyncio
from datetime import datetime
from geeknews.hackernews.config import HackernewsConfig
from geeknews.hackernews.data_path import HackernewsDataPathManager
from geeknews.utils.logger import LOG
from geeknews.utils.date import GeeknewsDate


HN_MAX_DOWNLOADS = 100
HN_RECENT_HOURS = 24


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
        self.job_title_re = re.compile(r'\(YC\s\w\d+\)\s\w+\s[Hh]iring')

    def http_get(self, url, empty_data=[]):
        response = requests.get(url)
        try:
            response.raise_for_status()
            return response.json()
        except Exception as e:
            LOG.error(str(e))
            return empty_data
    
    def fetch_top_story_ids(self):
        return self.http_get(self.api.top_stories_url(), empty_data=[])
    
    def fetch_new_story_ids(self):
        return self.http_get(self.api.new_stories_url(), empty_data=[])
    
    def fetch_item(self, id):
        url = self.api.get_item_url(id)
        return self.http_get(url, empty_data={})
        
    def get_item(self, id, item_type='story', parent_id=None, recursive=False, remain_comment_count=10, current_num=0, mark_article=False, date=GeeknewsDate.now()):
        item = self.get_local_item(id, date)
        
        if not item:
            action_log = '开始下载'
            item = self.fetch_item(id)
            self.save_item(id, item, date)
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
                date=date,
            )
            comments.append(comment)

        del item['kids']
        if comments:
            item['comments'] = comments
        
        return item
    
    def fetch_daily_stories(self, date=GeeknewsDate.now()):
        # fetch and save top stories json
        stories = self.fetch_top_stories(date)
        stories_file_path = self.datapath_manager.get_stories_file_path(name='topstories', date=date)
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
                    'url': story.get('url', self.get_default_story_url(story['id'])),
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

    def fetch_top_stories(self, date=GeeknewsDate.now()):
        story_limit = self.config.daily_story_max_count
        comment_limit = self.config.each_story_max_comment_count if self.config.summary_with_comments else 0
        article_limit = self.config.daily_article_max_count

        LOG.debug(f'开始请求top stories')
        story_ids = self.fetch_top_story_ids()
        story_ids = self.custom_rank_ids(story_ids, date=date, priority=True)
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
                recursive=mark_article if self.config.summary_with_comments else False,
                remain_comment_count=comment_limit if mark_article else 0,
                current_num=current_num,
                mark_article=mark_article,
                date=date,
            )
            items.append(item)
        return items
    
    def get_story_id_with_highest_score(self, category='topstories', article_only=True, date=GeeknewsDate.now()):
        # default implementation: 
        # get topstories.json, look for story with both highest score and marked article

        story_list_path = self.datapath_manager.get_stories_file_path(name=category, date=date)
        if not os.path.exists(story_list_path):
            LOG.error('搜索最高分热点失败: 找不到topstories.json')
            return -1
        
        with open(story_list_path) as f:
            stories = json.load(f)

        if not isinstance(stories, list) or not stories:
            LOG.error('搜索最高分热点失败: 没有热点数据')
            return -1

        highest_score = 0
        found_story_id = -1
        
        for story in stories:
            article = story.get('article', False)
            score = story.get('score', 0)
            if article_only and not article:
                continue
            if score > highest_score:
                highest_score = score
                found_story_id = story.get('id', 0)

        # if no highest score, then get first story.
        if highest_score == 0:
            first_story = stories[0]
            found_story_id = first_story.get('id', 0)
        
        return found_story_id
    
    def get_local_item(self, id, date=GeeknewsDate.now()):
        story_path = self.get_story_path(id, date)
        if os.path.exists(story_path):
            with open(story_path) as f:
                return json.load(f)
        return {}
    
    def save_item(self, id, item, date=GeeknewsDate.now()):
        story_path = self.get_story_path(id, date)
        story_dir = os.path.dirname(story_path)
        if not os.path.exists(story_dir):
            os.makedirs(story_dir)
        with open(story_path, 'w') as f:
            json.dump(item, f, ensure_ascii=False)

    def get_story_path(self, id, date=GeeknewsDate.now()):
        return self.datapath_manager.get_story_file_path(id, date)

    @staticmethod
    def get_default_story_url(story_id):
        return f'https://news.ycombinator.com/item?id={story_id}'
    
    async def fetch_url(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()
        except Exception as e:
            LOG.error(f"下载失败: {e}")
            return {}
    
    async def aio_fetch_stories(self, story_ids, date):
        tasks = []
        for id in story_ids:
            task = asyncio.create_task(self.aio_fetch_story(id, date))
            tasks.append(task)
        result = await asyncio.gather(*tasks)
        return result
    
    async def aio_fetch_story(self, id, date):
        story = await self.aio_get_local_item(id, date)
        if not story:
            # LOG.debug(f"开始下载story_id: {id}")
            url = self.api.get_item_url(id)
            story = await self.fetch_url(url)
            if story:
                await self.aio_save_item(id, story, date)
        return story

    async def aio_get_local_item(self, id, date):
        story_path = self.get_story_path(id, date)
        if not os.path.exists(story_path):
            return {}
        # LOG.debug(f"本地读取已下载的story_id: {id}")
        async with aiofiles.open(story_path) as f:
            text = await f.read()
            return json.loads(text)

    async def aio_save_item(self, id, item, date):
        story_path = self.get_story_path(id, date)
        story_dir = os.path.dirname(story_path)
        if not os.path.exists(story_dir):
            os.makedirs(story_dir)
        # LOG.debug(f"保存下载的story_id: {id}")
        async with aiofiles.open(story_path, 'w') as f:
            text = json.dumps(item, ensure_ascii=False)
            await f.write(text)

    def prefetch_stories(self, story_ids, date):
        stories = []
        for id in story_ids:
            story = self.get_local_item(id, date)
            if not story:
                story = self.fetch_item(id)
                self.save_item(id, story, date)
            stories.append(story)
        return stories
    
    def custom_rank_ids(self, story_ids, date=GeeknewsDate.now(), priority=True):
        # get first batch ids and fetch details, filter in recent hours and sort by score
        max_downloads = HN_MAX_DOWNLOADS

        if max_downloads == 0:
            return story_ids

        stories = []
        story_ids = story_ids[:max_downloads]

        if self.config.story_fetch_concurrent:
            stories = asyncio.run(self.aio_fetch_stories(story_ids, date))
        else:
            stories = self.prefetch_stories(story_ids, date)
        
        if priority:
            stories = self.apply_sort_rule(stories, date)
        stories = self.custom_rank_stories(stories, priority=priority)
        return list(map(lambda x: x.get('id', 0), stories))
    
    def custom_rank_stories(self, stories, priority=True):
        stories = list(filter(self.should_keep_story, stories))
        stories.sort(key=lambda x: x.get('score', 0), reverse=True)
        if priority:
            stories = self.up_high_priority_stories(stories)
            stories = self.sink_low_priority_stories(stories)
        stories = self.sink_unsupport_stories(stories)
        return stories
    
    def should_keep_story(self, story: dict):
        if not self.is_recent_story(story, HN_RECENT_HOURS):
            return False
        if self.is_job_hiring(story):
            return False
        return True
    
    def is_job_hiring(self, story: dict):
        title = story.get('title', '')
        if not title:
            return False
        
        job_title = self.job_title_re.search(title)
        return True if job_title else False

    def is_recent_story(self, story: dict, in_hours: int):
        timestamp = story.get('time', 0)
        return self.is_recent(timestamp, in_hours)

    @staticmethod
    def is_recent(timestamp: int, in_hours: int):
        date = datetime.fromtimestamp(timestamp)
        time_diff = datetime.now() - date
        return int(time_diff.total_seconds()) // (3600 * in_hours) == 0
    
    def sink_unsupport_stories(self, stories: list):
        '''move unsupport stories to the end of interpretable articles.'''
        
        end_index = self.config.daily_article_max_count
        if end_index >= len(stories):
            return stories
        
        stories = self.move_elements_down(
            arr=stories, 
            index=end_index, 
            condition=self.uninterpretable_story
        )
        
        return stories
    
    def uninterpretable_story(self, story):
        '''不可解读的story'''
        title = story.get('title', '').strip()
        url = story.get('url', '').strip()

        is_question = title.startswith('Ask HN:')
        is_video = title.endswith('[video]')
        is_pdf = url.endswith('.pdf') or url.startswith('https://arxiv.org/pdf/')

        return is_question or is_pdf or is_video
    
    def sink_low_priority_stories(self, stories):
        end_index = self.config.daily_article_max_count
        if end_index >= len(stories):
            return stories
        
        stories = self.move_elements_down(
            arr=stories, 
            index=end_index, 
            condition=lambda s: s.get('priority', '') == 'low'
        )
        
        return stories
    
    def up_high_priority_stories(self, stories):
        end_index = self.config.daily_article_max_count
        if end_index >= len(stories):
            return stories
        
        stories = self.move_elements_up(
            arr=stories, 
            index=end_index, 
            condition=lambda s: s.get('priority', '') == 'high'
        )
        
        return stories
    
    @staticmethod
    def move_elements_down(arr, index, condition):
        '''find all elements in certain condition before a given index and move them after that index with ordering unchanged.'''
        # Generated by deepseek-coder-v2:16b
        if index >= len(arr) or index < 0:
            return arr
        
        # Extract elements to be moved
        elements_to_move = [arr[i] for i in range(len(arr)) if i < index and condition(arr[i])]
        
        # Remove these elements from the original array
        arr = [arr[i] for i in range(len(arr)) if i >= index or not condition(arr[i])]
        
        # Insert the moved elements after the given index
        arr[index:] = elements_to_move + arr[index:]
        
        return arr

    @staticmethod
    def move_elements_up(arr, index, condition):
        if index < 0 or index >= len(arr):
            return arr
        # Extract elements to be moved
        elements_to_move = [arr[i] for i in range(len(arr)) if i > index and condition(arr[i])]
        # Remove these elements from the original array
        arr = [arr[i] for i in range(len(arr)) if i <= index or not condition(arr[i])]
        # Insert the moved elements before the given index
        arr[:index] = arr[:index] + elements_to_move
        return arr
    
    def clean_local_items(self, date):
        story_dir = self.datapath_manager.get_story_date_dir(date)
        item_names = os.listdir(story_dir)
        for filename in item_names:
            name, ext = os.path.splitext(filename)
            if name.isdigit() and ext == '.json':
                item_path = os.path.join(story_dir, filename)
                os.remove(item_path)
    
    def get_preview(self, date=GeeknewsDate.now(), priority=True):
        # fetch stories and rank them
        story_ids = self.fetch_top_story_ids()
        story_ids = self.custom_rank_ids(story_ids, date, priority)
        
        # get story list
        stories = []
        for index, id in enumerate(story_ids):
            story_path = self.datapath_manager.get_story_file_path(id, date)
            if os.path.exists(story_path):
                with open(story_path) as f:
                    story = json.load(f)
                
                simple_story = {
                    "id": story["id"],
                    "title": story["title"],
                    "score": story["score"],
                }
                stories.append(simple_story)
        
        # save story list
        story_dir = self.datapath_manager.get_story_date_dir(date)
        preview_path = os.path.join(story_dir, 'preview.json')
        with open(preview_path, 'w') as f:
            json.dump(stories, f, ensure_ascii=False)
        
        return preview_path
    
    def apply_sort_rule(self, stories, date=GeeknewsDate.now()):
        '''Read "sort_rule.json" then mark it to story list'''
        story_dir = self.datapath_manager.get_story_date_dir(date)
        rule_path = os.path.join(story_dir, 'sort_rule.json')
        if not os.path.exists(rule_path):
            return stories
        
        with open(rule_path) as f:
            rule = json.load(f)
        
        if 'priority' in rule:
            priority = rule['priority']
            high_ids = set(priority.get('high', []))
            low_ids = set(priority.get('low', []))
            
            for story in stories:
                if story['id'] in high_ids:
                    story['priority'] = 'high'
                elif story['id'] in low_ids:
                    story['priority'] = 'low'
        
        return stories
    
    def make_priority_rule(self, rule_text, date):
        if ';' not in rule_text or ':' not in rule_text:
            return ""
        
        rules = rule_text.split(';')
        action_rule = "override"
        high_ids = set()
        low_ids = set()

        story_dir = self.datapath_manager.get_story_date_dir(date)
        rule_path = os.path.join(story_dir, 'sort_rule.json')

        summary_dir = self.datapath_manager.get_summary_full_dir(locale='zh_cn', date=date)
        trans_preview_path = os.path.join(summary_dir, 'preview.md')
        if not os.path.exists(trans_preview_path):
            LOG.error("未找到预览列表")
            return ""
        
        with open(trans_preview_path) as f:
            preview_text = f.read()
        
        preview_id_mappings = {}
        preview_list = preview_text.split('\n')
        regex = re.compile(r'^(?P<num>\d+)\.\s?\[(?P<id>\d+)\]\s?')
        for preview_item in preview_list:
            matched_item = regex.search(preview_item)
            if not matched_item:
                continue
            num_text = matched_item.group('num')
            id_text = matched_item.group('id')
            preview_id_mappings[num_text] = int(id_text)

        for rule in rules:
            components = rule.split(':')
            if len(components) != 2:
                continue
            
            rule_name = components[0]
            rule_value = components[1]
            
            if rule_name == 'low' or rule_name == 'high':
                nums = rule_value.split(',')
                for num in nums:
                    id = preview_id_mappings.get(num, '')
                    if not isinstance(id, int) or id <= 0:
                        continue
                    if rule_name == 'low':
                        low_ids.add(id)
                    else:
                        high_ids.add(id)
            elif rule_name == 'action':
                action_rule = rule_value

        rule_content = {}
        if os.path.exists(rule_path):
            with open(rule_path) as f:
                rule_content = json.load(f)

        priority = rule_content.get('priority', {})
        if action_rule == 'append':
            existed_high_ids = set(priority.get('high', []))
            existed_low_ids = set(priority.get('low', []))
            high_ids = high_ids.union(existed_high_ids)
            low_ids = low_ids.union(existed_low_ids)
        
        priority['low'] = list(low_ids)
        priority['high'] = list(high_ids)
        rule_content['priority'] = priority
        
        with open(rule_path, 'w') as f:
            json.dump(rule_content, f)

        return rule_path


def test_hackernews_client():
    config = HackernewsConfig.get_from_parser()
    dpm = HackernewsDataPathManager(config)
    client = HackernewsClient(config=config, datapath_manager=dpm)
    client.fetch_daily_stories()
