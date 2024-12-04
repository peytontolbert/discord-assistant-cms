from openai import OpenAI


class TextManager:  
    def __init__(self, apikey):
        self.client = OpenAI(api_key=apikey)

    def text_to_text(self, system_prompt, user_prompt):
        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
    messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        )
        return completion.choices[0].message
