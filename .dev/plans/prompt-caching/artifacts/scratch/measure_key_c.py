import sys
from pathlib import Path

sys.path.insert(0, ".")
from bishop_shared.profile_renderer import load_profile, render_profile_prompt
from bishop_shared.rubric_assets import load_rubric
import tiktoken

enc = tiktoken.get_encoding("cl100k_base")
doc = load_profile(Path("config/profiles/professional_v1.0.0.yaml"))
rendered_false = render_profile_prompt(doc, include_output=False)
profile_tokens = len(enc.encode(rendered_false))

rubric_path = Path("config/prompts/call2_rubric_v1.md")
rubric_doc = load_rubric(rubric_path)
annex_tokens = len(enc.encode(rubric_doc.body))

instructions = (
    "Evaluate the relevance of the provided content to the profile above.\n"
    "Respond only with a valid JSON object matching the schema below.\n\n"
    "Schema:\n"
    "{\n"
    '  "relevance_score": float,\n'
    '  "relevance_reason": "string, one sentence, why this is or is not relevant",\n'
    '  "value_rationale": "string, 1-2 sentences, what specific value this provides '
    "to the profile's owner\"\n"
    "}"
)
instr_tokens = len(enc.encode(instructions))
total = profile_tokens + annex_tokens + instr_tokens
print("profile(false) tokens:", profile_tokens)
print("annex tokens:", annex_tokens)
print("instructions tokens:", instr_tokens)
print("total:", total)
print("margin over 4506:", total - 4506)
