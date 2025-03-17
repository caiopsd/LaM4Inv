from enum import Enum

from openai import OpenAI

from llm.llm import LLM

class ChatGPTModel(Enum):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"

class ChatGPT(LLM):
    def __init__(self, api_key: str, model: ChatGPTModel):
        self.model = model
        self.client = self._get_openai_client(api_key)
    
    def _get_openai_client(self, api_key: str) -> OpenAI:
        return OpenAI(
            api_key=api_key,  
        )
    
    def prompt(self, prompt: str) -> str:
        completions = self.client.chat.completions.create(
            model=self.model.value,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        return completions.choices[0].message.content
