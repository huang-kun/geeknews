import json
import requests
from geeknews.utils.logger import LOG


WPP_TAG = '[公众号]'


class WppBaseApi:

    def __init__(self):
        self.base_url = 'https://api.weixin.qq.com'
        self.common_path = '/cgi-bin' 

    def log_name(self):
        return 'base'

    def method(self):
        return 'POST'
    
    def api_path(self):
        return ''
    
    def url_params(self):
        return {}
    
    def headers(self):
        return {}
    
    def post_param_name(self):
        return 'json'
    
    def post_param_value(self):
        return {}
    
    def full_url(self):
        url = self.base_url + self.common_path + self.api_path()
        p = self.url_params()
        ps = '&'.join([f'{k}={v}' for k, v in p.items()]) if p else ''
        return url + '?' + ps if ps else url
    
    def full_request_params(self):
        method = self.method()
        if method == 'GET':
            return self.full_get_params()
        elif method == 'POST':
            return self.full_post_params()
        else:
            return {}
    
    def full_get_params(self):
        return {
            'url': self.full_url()
        }
    
    def full_post_params(self):
        params = {
            'url': self.full_url()
        }
        
        headers = self.headers()
        name = self.post_param_name()
        value = self.post_param_value()

        if name == 'data':
            jstr = json.dumps(value, ensure_ascii=False)
            params[name] = jstr.encode("utf-8")
        else:
            params[name] = value
        
        if headers:
            params['headers'] = headers
        
        return params


class WppGetTokenApi(WppBaseApi):
    '''获取access_token'''
    # https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html

    def __init__(self, app_id, app_secret):
        super().__init__()
        self.app_id = app_id
        self.app_secret = app_secret

    def log_name(self):
        return '获取token'

    def method(self):
        return 'GET'
    
    def api_path(self):
        return '/token'
    
    def url_params(self):
        return {
            'grant_type': 'client_credential',
            'appid': self.app_id,
            'secret': self.app_secret
        }
    

class WppTokenBaseApi(WppBaseApi):
    
    def __init__(self, access_token):
        super().__init__()
        self.access_token = access_token

    def url_params(self):
        return {
            'access_token': self.access_token
        }
