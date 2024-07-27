import pathlib
import textwrap

import google.generativeai as genai

GOOGLE_API_KEY='AIzaSyAWczIb0hD7XU5R5djXp4nzzeLq_IkaFcc'

genai.configure(api_key=GOOGLE_API_KEY)

for m in genai.list_models():
  if 'generateContent' in m.supported_generation_methods:
    print(m.name)