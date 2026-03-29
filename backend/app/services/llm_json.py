import json
import re


def parse_llm_json_text(text: str):
    text = (text or '').strip()
    if not text:
        raise ValueError('Empty LLM response')
    try:
        return json.loads(text)
    except Exception:
        pass

    fenced = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
        return json.loads(candidate)

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise ValueError('Unable to parse JSON from LLM response')
