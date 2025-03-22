from enum import Enum

from llm.llm import LLM, ChatOptions, Chat

class TransformersModel(Enum):
    pass

class LlamaModel(TransformersModel):
    LLAMA_3_8B = 'meta-llama/Meta-Llama-3-8B-Instruct'

class Transformers(LLM):
    def __init__(self, model: LlamaModel):
        import torch
        from transformers import pipeline
        
        self.model = model
        self._pipeline = pipeline("text-generation", model.value, torch_dtype=torch.bfloat16, device_map="auto")
    
    def _get_messages(self, chat: Chat) -> list:
        return [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in chat.messages
        ]

    def chat(self, chat: Chat, options: ChatOptions = None) -> str:
        response = self._pipeline(self._get_messages(chat), max_new_tokens=512)
        content = response[0]["generated_text"][-1]["content"]
        return content
