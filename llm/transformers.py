from enum import Enum

import torch
from transformers import pipeline

from llm.llm import LLM

class TransformersModel(Enum):
    LLAMA_3_8B = 'meta-llama/Meta-Llama-3-8B-Instruct'

class Transformers(LLM):
    def __init__(self, model: TransformersModel, system_instructions: str = None):
        self.model = model
        self._pipeline = pipeline("text-generation", model.value, torch_dtype=torch.bfloat16, device_map="auto")
        self.messages = []
        if system_instructions:
            self._add_system_instructions(system_instructions)
    
    def _get_messages(self) -> list:
        return self.messages
    
    def _add_system_instructions(self, instructions: str):
        self.messages.append({"role": "system", "content": instructions})
    
    def _add_assistant_response(self, response: str):
        self.messages.append({"role": "assistant", "content": response})

    def _add_user_message(self, message: str):
        self.messages.append({"role": "user", "content": message})
    
    def clear(self):
        self.messages = []

    def chat(self, message: str) -> str:
        self._add_user_message(message)

        response = self._pipeline(self.messages, max_new_tokens=512)
        content = response[0]["generated_text"][-1]["content"]

        self._add_assistant_response(content)

        return content
