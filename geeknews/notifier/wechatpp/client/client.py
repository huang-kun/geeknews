
from geeknews.config import GeeknewsWechatPPConfig
from geeknews.notifier.wechatpp.client.base import WppRequest, WppBaseClient
from geeknews.notifier.wechatpp.api.draft import *
from geeknews.notifier.wechatpp.api.material import *
from geeknews.notifier.wechatpp.api.publish import *


class WppClient(WppBaseClient):

    def batch_get_material(self):
        api = WppMaterialBatchGetApi(self.access_token, type='image')
        result = self.send(api)
        return result
    
    def add_draft(self, article: WppDraftArticle):
        api = WppDraftAddArticleApi(self.access_token, article)
        return self.send(api)

    def batch_get_drafts(self):
        api = WppDraftBatchGetApi(self.access_token)
        return self.send(api)
    
    def publish(self, media_id):
        api = WppPublishSubmitApi(self.access_token, media_id)
        result = self.send(api)
        return result.get('publish_id', '')
    
    def get_publish_status(self, publish_id, poll=False):
        '''发布状态, 0:成功, 1:发布中, 2:原创失败, 3: 常规失败, 4:平台审核不通过, 5:成功后用户删除所有文章, 6: 成功后系统封禁所有文章'''
        api = WppPublishPollApi(self.access_token, publish_id)
        result = self.send(api)
        status = result.get('publish_status', -1)
        if status == -1:
            return result
        return result


def test_wpp_client():
    config = GeeknewsWechatPPConfig.get_from_parser()
    client = WppClient(config)
    print(client.batch_get_drafts())