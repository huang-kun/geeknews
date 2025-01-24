import os
from geeknews.notifier.wechatpp.api.base import WppTokenBaseApi


class WppMeterialAddApi(WppTokenBaseApi):
    '''新增其他类型永久素材'''
    # https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/Adding_Permanent_Assets.html

    def __init__(self, access_token, media_path, title='', intro='', type='image'):
        super().__init__(access_token)
        
        filename = os.path.basename(media_path)
        name, ext = os.path.splitext(filename)

        self.media_path = media_path
        self.title = title if title else name
        self.intro = intro
        self.type = type

    def log_name(self):
        return '新增其他类型永久素材'
    
    def api_path(self):
        return '/material/add_material'
    
    def url_params(self):
        params = super().url_params()
        params['type'] = self.type
        return params
    
    def post_param_name(self):
        return 'files'
    
    def post_param_value(self):
        desc = '{"title":"TITLE", "introduction":"INTRODUCTION"}'
        desc = desc.replace('TITLE', self.title)
        desc = desc.replace('INTRODUCTION', self.intro)

        return {
            'media': open(self.media_path, 'rb'),
            'description': (None, desc),
        }


class WppMaterialBatchGetApi(WppTokenBaseApi):
    '''获取素材列表'''
    # https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/Get_materials_list.html

    def __init__(self, access_token, type='news', offset=0, count=20):
        super().__init__(access_token)
        self.type = type
        self.offset = offset
        self.count = count
    
    def log_name(self):
        return '获取素材列表'

    def api_path(self):
        return '/material/batchget_material'
    
    def post_param_value(self):
        return {
            'type': self.type,
            'offset': self.offset,
            'count': self.count,
        }