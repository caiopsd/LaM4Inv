from enum import Enum

from openai import OpenAI as OpenAIClient, NOT_GIVEN

from llm.llm import LLM, ChatOptions, Chat

class OpenAIModel(Enum):
    pass

class ChatGPTModel(OpenAIModel):
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_O1_MINI = "o1-mini"

class DeepseekModel(OpenAIModel):
    DEEPSEEK_R1 = "deepseek-reasoner"

class OpenAI(LLM):
    def __init__(self, model: OpenAIModel, api_key: str = None, base_url: str = None):
        self.model = model
        self.client = OpenAIClient(api_key=api_key, base_url=base_url)

    def _get_messages(self, chat: Chat) -> list:
        return [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in chat.messages
        ]

    def chat(self, chat: Chat, options: ChatOptions = None) -> str:
        completions = self.client.chat.completions.create(
            model=self.model.value,
            messages=self._get_messages(chat),
            presence_penalty=2*options.presence_penalty if options and options.presence_penalty else NOT_GIVEN,
        )
        response = completions.choices[0].message.content
        return response
