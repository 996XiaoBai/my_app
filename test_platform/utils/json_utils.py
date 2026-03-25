import json
import re
import logging

logger = logging.getLogger(__name__)

def parse_json_markdown(json_string):
    """
    Parses a JSON string that might be wrapped in markdown code blocks.
    Tries to be robust against common issues.
    """
    if not json_string:
        return None

    # Remove markdown code blocks
    cleaned = json_string.strip()
    if cleaned.startswith("```"):
        # Match ```json ... ``` or just ``` ... ```
        pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
        else:
            # Fallback: remove first and last lines if they look like ```
            lines = cleaned.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)
    
    cleaned = cleaned.strip()
    
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning(f"Standard JSON parse failed: {e}. Attempting repair...")
        # Attempt simple repairs
        # 1. Remove trailing commas in objects/lists (common LLM error)
        cleaned_repaired = re.sub(r",\s*([\]}])", r"\1", cleaned)
        try:
            return json.loads(cleaned_repaired)
        except json.JSONDecodeError:
            pass

        # If still failing, return None or consider using a heavy library like json_repair
        # For now, return None to signal failure
        logger.error(f"JSON parsing failed after repair attempts. Content snippet: {cleaned[:100]}...")
        return None
