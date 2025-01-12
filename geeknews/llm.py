import os
import httpx
from openai import OpenAI
from geeknews.utils.logger import LOG

class LLM:

    def __init__(self):
        self.client = self.create_openai_client()
        self.model = 'gpt-4o-mini'

    @staticmethod
    def create_openai_client():
        api_key = os.environ["OPENAI_API_KEY"]
        if "OPENAI_BASE_URL" in os.environ:
            base_url = os.environ['OPENAI_BASE_URL']
            return OpenAI(
                base_url=base_url,
                api_key=api_key,
                http_client=httpx.Client(
                    base_url=base_url,
                    follow_redirects=True,
                )
            )
        else:
            return OpenAI(api_key=api_key)
        
    def is_image_url(self, url):
        for ext in ['.png', '.jpeg', '.jpg']:
            if url.endswith(ext):
                return True
        return False

    def read_image_content(self, image_url):
        """
        理解图片内容
        https://platform.openai.com/docs/guides/vision?lang=node
        """
        if self.model != 'openai' or not self.is_image_url(image_url):
            return None
        
        response = self.client.chat.completions.create(
            model=self.config.openai_model_name,  # 使用配置中的OpenAI模型名称
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant for understanding image."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text", 
                            "text": "What's in this image?"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )

        choice = response.choices[0]
        return choice.message.content
    
    def get_assistant_message(self, system_prompt, user_content):
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content}
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            LOG.error(f"请求大模型时发生错误: {e}")
            return ''


def test_llm():
    llm = LLM()
    msg = llm.get_assistant_message(
        system_prompt='You are a help assistant',
        user_content='Hello',
    )