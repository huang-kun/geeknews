import os
import httpx
from openai import OpenAI, AsyncOpenAI
from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions

from geeknews.utils.logger import LOG

class LLM:

    prompt_map = {}

    def __init__(self, api_key=None, base_url=None, model='gpt-4o'):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.openai_client = self.create_openai_client()
        self.gemini_client = self.create_gemini_client()
        self.aio_openai_client = self.create_aio_openai_client()

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
    
    def create_aio_openai_client(self):
        api_key = self.get_config_value(self.api_key, 'OPENAI_API_KEY')
        base_url = self.get_config_value(self.base_url, 'OPENAI_BASE_URL')

        if base_url:
            return AsyncOpenAI(
                base_url=base_url,
                api_key=api_key,
                http_client=httpx.AsyncClient(
                    base_url=base_url,
                    follow_redirects=True,
                )
            )
        else:
            return AsyncOpenAI(api_key=api_key)
    
    def create_gemini_client(self):
        gemini_api_key = os.getenv('GEMINI_API_KEY', '')
        if not gemini_api_key:
            return None
        
        return genai.Client(
            api_key=gemini_api_key, 
            # http_options=HttpOptions(api_version="v1")
        )
        
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
        
        response = self.openai_client.chat.completions.create(
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
    
    def generate_text(self, system_prompt, user_content, model):
        if model.startswith('gemini') and self.gemini_client:
            return self.get_gemini_text(system_prompt, user_content, model)
        else:
            return self.get_assistant_message(system_prompt, user_content)
    
    def get_assistant_message(self, system_prompt, user_content, model=None):
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content}
        ]
        try:
            response = self.openai_client.chat.completions.create(
                model=model if model else self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            LOG.error(f"请求openai出错: {e}")
            return ''
        
    def get_gemini_text(self, system_prompt, user_content, model):
        try:
            response = self.gemini_client.models.generate_content(
                model=model, 
                contents=user_content, 
                config=GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_modalities=["TEXT"],
                ),
            )
            return response.text
        except Exception as e:
            LOG.error(f"请求gemini出错: {e}")
            return ''

    async def aio_generate_text(self, system_prompt, user_content, model):
        if model.startswith('gemini') and self.gemini_client:
            return await self.aio_get_gemini_text(system_prompt, user_content, model)
        else:
            return await self.aio_get_assistant_message(system_prompt, user_content) 

    async def aio_get_assistant_message(self, system_prompt, user_content, model=None):
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content}
        ]
        try:
            response = await self.aio_openai_client.chat.completions.create(
                model=model if model else self.model,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            LOG.error(f"请求openai出错: {e}")
            return ''

    async def aio_get_gemini_text(self, system_prompt, user_content, model):
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model=model,
                contents=user_content,
                config=GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_modalities=["TEXT"],
                ),
            )
            return response.text
        except Exception as e:
            LOG.error(f"请求gemini出错: {e}")
            return ''


def test_llm():
    llm = LLM()
    msg = llm.get_gemini_text(
        system_prompt='You are a helpful assistant.',
        user_content='hello',
        model='gemini-2.0-flash'
    )
    print(msg)


if __name__ == '__main__':
    test_llm()