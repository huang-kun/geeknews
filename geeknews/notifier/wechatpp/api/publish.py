
from geeknews.notifier.wechatpp.api.base import WppTokenBaseApi


class WppPublishSubmitApi(WppTokenBaseApi):
    '''发布接口'''
    # https://developers.weixin.qq.com/doc/offiaccount/Publish/Publish.html

    def __init__(self, access_token, media_id):
        super().__init__(access_token)
        self.media_id = media_id

    def log_name(self):
        return '发布接口'
    
    def api_path(self):
        return '/freepublish/submit'
    
    def post_param_value(self):
        return {
            'media_id': self.media_id,
        }
    

class WppPublishPollApi(WppTokenBaseApi):
    '''发布状态轮询接口'''
    # https://developers.weixin.qq.com/doc/offiaccount/Publish/Get_status.html

    def __init__(self, access_token, publish_id):
        super().__init__(access_token)
        self.publish_id = publish_id
    
    def log_name(self):
        return '发布状态轮询接口'
    
    def api_path(self):
        return '/freepublish/get'
    
    def post_param_value(self):
        return {
            'publish_id': self.publish_id,
        }
    
    
