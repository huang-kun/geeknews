from typing import List
from geeknews.notifier.wechatpp.api.base import WppTokenBaseApi


class WppDraftArticle:
    '''图文消息结构'''

    def __init__(self, title, author, content, thumb_media_id, need_open_comment=1, only_fans_can_comment=0):
        self.title = title
        self.author = author
        self.content = content
        self.thumb_media_id = thumb_media_id
        self.need_open_comment = need_open_comment
        self.only_fans_can_comment = only_fans_can_comment
    
    def to_params(self):
        return {
            "article_type": "news",
            "title": self.title,
            "author": self.author,
            "content": self.content,
            'thumb_media_id': self.thumb_media_id,
            "need_open_comment": self.need_open_comment,
            "only_fans_can_comment": self.only_fans_can_comment,
        }


class WppDraftImage:
    '''图片消息结构'''

    def to_params(self):
        return {}


class WppDraftAddArticleApi(WppTokenBaseApi):
    '''新建草稿'''
    # https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html

    def __init__(self, access_token: str, article: WppDraftArticle=None, image: WppDraftImage=None):
        super().__init__(access_token)
        self.article = article
        self.image = image

    def log_name(self):
        return '新建文章草稿'
    
    def api_path(self):
        return '/draft/add'
    
    def post_param_name(self):
        return 'data'
    
    def post_param_value(self):
        articles = []

        if self.article:
            articles.append(self.article.to_params())

        if self.image:
            articles.append(self.image.to_params())

        return {
            "articles": articles
        }


class WppDraftBatchGetApi(WppTokenBaseApi):
    '''获取草稿列表'''
    # https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Get_draft_list.html

    def __init__(self, access_token, offset=0, count=20, no_content=1):
        super().__init__(access_token)
        self.offset = offset
        self.count = count
        self.no_content = no_content
    
    def log_name(self):
        return '获取草稿列表'
    
    def api_path(self):
        return '/draft/batchget'
    
    def post_param_value(self):
        return {
            'offset': self.offset,
            'count': self.count,
            'no_content': self.no_content,
        }