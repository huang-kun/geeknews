import os
import json

from datetime import datetime, timedelta

from geeknews.config import GeeknewsWechatPPConfig
from geeknews.utils.logger import LOG

from geeknews.notifier.wechatpp.api.base import *


class WppRequest:

    @staticmethod
    def send(api: WppBaseApi):
        req_func = None

        log_prefix = WPP_TAG + api.log_name()
        method = api.method()

        if method == 'POST':
            req_func = requests.post
        elif method == 'GET':
            req_func = requests.get

        if req_func is None:
            return {}
        
        try:
            response = req_func(**api.full_request_params())
            response.raise_for_status()
        except Exception as e:
            LOG.error(f'{log_prefix}失败: {e}')
        else:
            result = response.json()
            if 'errcode' in result:
                error_code = result['errcode']
                if isinstance(error_code, int) and error_code != 0:
                    LOG.error(f'{log_prefix}报错: {json.dumps(result)}')
                return result
            else:
                return result
        return {}


class WppBaseClient:

    def __init__(self, config: GeeknewsWechatPPConfig):
        self.app_id = os.getenv('WECHATPP_APP_ID', '')
        self.app_secret = os.getenv('WECHATPP_APP_SECRET', '')
        self.config = config

        self.access_token = ''
        self.expire_date = None

        if os.path.exists(config.access_token_path):
            with open(config.access_token_path) as f:
                contents = json.load(f)
                self.access_token = contents.get('access_token', '')

                expire_date_str = contents.get('expire_date', '')
                if expire_date_str:
                    self.expire_date = datetime.fromisoformat(expire_date_str)
        else:
            token_dir = os.path.dirname(config.access_token_path)
            if not os.path.exists(token_dir):
                os.makedirs(token_dir)
    
    def is_token_valid(self):
        if not self.access_token:
            LOG.debug(f"{WPP_TAG}没有请求token")
            return False
        if not self.expire_date:
            return False
        if not isinstance(self.expire_date, datetime):
            return False
        
        now = datetime.now().astimezone()
        valid = now < self.expire_date

        if not valid:
            LOG.debug(f"{WPP_TAG}token已过期")
        return valid
    
    def auto_refresh_token(self):
        if self.is_token_valid():
            return True
        self.fetch_access_token()
        valid = self.is_token_valid()
        if valid:
            LOG.debug(f"{WPP_TAG}刷新token成功")
        else:
            LOG.debug(f"{WPP_TAG}刷新token失败")
        return valid

    def fetch_access_token(self):
        api = WppGetTokenApi(
            app_id=self.app_id,
            app_secret=self.app_secret,
        )

        result = WppRequest.send(api)
        
        if not 'access_token' in result:
            return
        
        access_token = result['access_token']
        expires_in = result.get('expires_in', 7200)

        now = datetime.now().astimezone()
        expire_date = now + timedelta(seconds=expires_in)

        self.access_token = access_token
        self.expire_date = expire_date

        self.save_token_info()

    def save_token_info(self):
        info = {}

        token = self.access_token if self.access_token else ''
        info['access_token'] = token
        
        if self.expire_date:
            info['expire_date'] = self.expire_date.isoformat()

        with open(self.config.access_token_path, 'w') as f:
            json.dump(info, f)

    def send(self, api: WppTokenBaseApi):
        result = WppRequest.send(api)
        if 'errcode' in result:
            # access_token expired
            if result['errcode'] == 42001:
                if self.auto_refresh_token():
                    api.access_token = self.access_token
                    return self.send(api)
        else:
            return result
        
        return {}