from enum import Enum

from transformers import pipeline

from llm.llm import LLM

class TransformersModel(Enum):
    pass

class LlamaModel(TransformersModel):
    LLAMA_3_8B = 'meta-llama/Meta-Llama-3-8B'

class Transformers(LLM):
    def __init__(self, model: TransformersModel, developer_instructions: str = None):
        self.model = model
        self._pipeline = pipeline(task="text-generation", model=model.value)
        self.messages = []
    
    def _get_messages(self) -> list:
        return self.messages
    
    def _add_system_response(self, response: str):
        self.messages.append({"role": "system", "content": response})

    def _add_user_message(self, message: str):
        self.messages.append({"role": "user", "content": message})
    
    def clear(self):
        self.messages = []

    def chat(self, message: str) -> str:
        self._add_user_message(message)

        response = self._pipeline(self.messages, max_new_tokens=512)
        content = response[0]["generated_text"][-1]["content"]

        self._add_system_response(content)

        return response
