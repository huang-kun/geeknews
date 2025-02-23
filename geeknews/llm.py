import os
import httpx
from openai import OpenAI
from geeknews.utils.logger import LOG

class LLM:

    prompt_map = {}

    def __init__(self, api_key=None, base_url=None, model='gpt-4o'):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = self.create_openai_client()

    @classmethod
    def get_system_prompt_map(cls, subdir='hackernews'):
        if cls.prompt_map:
            return cls.prompt_map

        prompts_dir = os.path.join('prompts', subdir)

        for filename in os.listdir(prompts_dir):
            basename, ext = os.path.splitext(filename)
            if ext != '.txt':
                continue
            prompt_path = os.path.join(prompts_dir, filename)
            with open(prompt_path) as f:
                cls.prompt_map[basename] = f.read().strip()
        
        return cls.prompt_map
    
    @classmethod
    def get_system_prompt(cls, name, subdir='hackernews'):
        prompt_map = cls.get_system_prompt_map(subdir)
        return prompt_map.get(name, '')

    def create_openai_client(self):
        api_key = self.get_config_value(self.api_key, 'OPENAI_API_KEY')
        base_url = self.get_config_value(self.base_url, 'OPENAI_BASE_URL')

        if base_url:
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
        
    def get_config_value(self, value, default_key):
        if not value and default_key in os.environ:
            return os.getenv(default_key)
        return value

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
        system_prompt='You are an excellent prompting engineer',
        user_content='I would like to generate a prompt for the editors of a scientific article: your readers are mostly ordinary people who care about cutting-edge information, please use a user-friendly style to interpret the article, and you can use your personal style while preserving the facts, and avoid being too rigid.',
    )
    print(msg)


if __name__ == '__main__':
    test_llm()