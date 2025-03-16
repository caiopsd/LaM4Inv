from enum import Enum

import requests

from llm.llm import LLM

class LLamaModel(Enum):
    LLAMA_3_8B = 'meta-llama/Meta-Llama-3-8B'

class LLama(LLM):
    def __init__(self, model: LLamaModel, base_url: str = "http://localhost:8000"):
        self.model = model
        self.base_url = base_url

    def _request(self, prompt: str) -> dict:
        url = f'{self.base_url}/v1/completions'
        headers = {'Content-Type': 'application/json'}
        payload = {'model': self.model.value, 'prompt': prompt}

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

    def prompt(self, prompt: str) -> str:
        response_data = self._request(prompt)
        return response_data.get("choices", [{}])[0].get("text", "")
