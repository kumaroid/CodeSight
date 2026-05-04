import os
from gigachat import GigaChat
from .promts import SYSTEM_PROMPT


class GigaChatArchitectureAdvisor:
    def __init__(self):
        self.client = GigaChat(
            credentials=os.getenv("AUTH_GC_KEY"),
            verify_ssl_certs=False,
            model=os.getenv("GIGACHAT_MODEL", "GigaChat-2-Pro"),
        )

    def recommend(self, user_prompt: str) -> str:
        response = self.client.chat(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            }
        )
        return response.choices[0].message.content
