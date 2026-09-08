"""
AI Quiz JSON Generator Service:
Calls local CLIProxy LLM (Gemini 3.6 Flash / GPT / Claude) to generate
custom structured Quiz JSON matching Quiz Engine V2 specifications:
1. QuizMystra 4-Cards (cards: id, label, image_prompt)
2. QuizMystra Visual Riddle (scene_prompt, clue_highlight, options)
3. Cyber Arcade Photo Reveal (choices: A, B, C, D, reveal_image_prompt)
4. Multi-Mode Dynamic Quiz
5. Script Preservation & Prompt Enrichment (enriching visual prompts without altering script)
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any
from pathlib import Path

from app.runtime_settings import load_runtime_settings
from app.settings import get_settings
from app.services.quiz_v2_contract import validate_questions


SYSTEM_PROMPT_QUIZ_ARCHITECT = """You are an expert viral YouTube & TikTok quiz producer.
Generate a strictly valid JSON array of quiz questions based on the user's topic and requested format.
CRITICAL RULE: DO NOT generate fake local filesystem paths. Generate descriptive, high-quality visual instructions ('image_prompt', 'scene_prompt', 'reveal_image_prompt') suitable for image generation models.

SUPPORTED FORMATS:

1. QuizMystra 4-Cards Comparison (WHO IS PREGNANT?, WHO IS GOING ON A DATE?, WHO IS THE KILLER?, WHO IS A BILLIONAIRE?):
[
  {
    "id": "q1",
    "question": "WHO IS PREGNANT?",
    "cards": [
      {"id": "1", "label": "DRINKING WINE", "image_prompt": "Close-up portrait of a chic woman holding a glass of red wine at a party"},
      {"id": "2", "label": "ESPRESSO SHOTS", "image_prompt": "A modern businesswoman drinking a double espresso shot at a cafe"},
      {"id": "3", "label": "PICKLES & ICE CREAM", "image_prompt": "A cheerful young woman snacking happily on dill pickles dipped in ice cream"},
      {"id": "4", "label": "RAW SUSHIS", "image_prompt": "A trendy person eating fresh salmon sashimi at a sushi bar"}
    ],
    "correct_option": "3",
    "explanation_text": "ANSWER: PERSON #3! SHE HAS STRANGE PREGNANCY CRAVINGS (PICKLES & SWEETS)!",
    "voice_q": "Look closely at these four women. Only one of them is pregnant! Can you spot who it is?",
    "voice_a": "Number 3 is pregnant! Alcohol, high caffeine, and raw fish are avoided during pregnancy, while pickles and ice cream is a classic craving!",
    "countdown_seconds": 8.0
  }
]

2. QuizMystra Visual Logic Riddle (Full-Screen Scene Anomaly):
[
  {
    "id": "riddle_01",
    "question": "WHO IS THE SLEEPWALKER?",
    "scene_prompt": "A detailed high-definition cutaway view of four bedrooms late at night. In room 3, a person is walking while clearly asleep, wearing two mismatched slippers (one bunny slipper, one leather loafer).",
    "options": ["1", "2", "3", "4"],
    "correct_option": "3",
    "clue_highlight": {
      "coord": [1200, 840],
      "radius": 80
    },
    "explanation_text": "ANSWER: PERSON 3! HE PUT ON TWO DIFFERENT SLIPPERS IN HIS SLEEP!",
    "voice_q": "Look closely at these four rooms late at night. One person is sleepwalking! Can you spot who it is?",
    "voice_a": "The sleepwalker is number 3! He put on two different slippers in his sleep!",
    "countdown_seconds": 8.0
  }
]

3. Multiple Choice with Photo Reveal:
[
  {
    "id": "q1",
    "question": "WHAT IS THE CAPITAL OF FRANCE?",
    "universe": "CAPITAL CITY",
    "choices": [
      {"id": "A", "text": "Lyon"},
      {"id": "B", "text": "Marseille"},
      {"id": "C", "text": "Paris"},
      {"id": "D", "text": "Nice"}
    ],
    "correct_id": "C",
    "answer_text": "PARIS",
    "reveal_image_prompt": "Iconic breathtaking aerial postcard view of the Eiffel Tower and Paris illuminated at twilight",
    "voice_q": "Geography test! What is the official capital city of France?",
    "voice_a": "Of course, it's Paris, the City of Light!",
    "countdown_seconds": 4.0
  }
]

RULES:
- Return ONLY the raw JSON array (no markdown backticks, no conversational text outside JSON).
- Each question must have a unique 'id' (e.g. 'q1', 'q2').
- 'countdown_seconds' must be a positive number between 3.0 and 15.0.
"""


def _call_cliproxy_llm(messages: list[dict[str, str]], temperature: float = 0.7, timeout: int = 45) -> str:
    """Helper to dispatch chat completion to configured CLIProxy endpoint."""
    rs = load_runtime_settings()
    s = get_settings()

    base_url = rs.cliproxy_base_url or s.cliproxy_base_url or "http://127.0.0.1:8317/v1"
    api_key = rs.cliproxy_api_key or s.cliproxy_api_key or ""
    model = rs.cliproxy_model or s.cliproxy_model or "gemini-3.6-flash-high"

    req_body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(req_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as res:
        res_data = json.loads(res.read().decode("utf-8"))
        return res_data["choices"][0]["message"]["content"].strip()


def _parse_and_clean_json(raw_text: str) -> list[dict[str, Any]]:
    """Robustly parse JSON array or questions dictionary from LLM response."""
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
        clean_text = re.sub(r"\n?```$", "", clean_text).strip()

    # Try exact json load first
    try:
        parsed = json.loads(clean_text)
    except Exception:
        # Match outermost bracket
        json_match = re.search(r"\[\s*\{.*\}\s*\]", clean_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(0))
        else:
            obj_match = re.search(r"\{\s*\"questions\".*\}", clean_text, re.DOTALL)
            if obj_match:
                parsed = json.loads(obj_match.group(0))
            else:
                raise ValueError(f"Could not extract valid JSON from LLM response:\n{raw_text[:200]}")

    if isinstance(parsed, dict):
        if "questions" in parsed and isinstance(parsed["questions"], list):
            parsed = parsed["questions"]
        elif "quiz" in parsed and isinstance(parsed["quiz"], list):
            parsed = parsed["quiz"]
        else:
            parsed = [parsed]

    if not isinstance(parsed, list):
        raise ValueError("LLM did not return a list of question objects")

    return parsed


def generate_quiz_json_with_ai(
    prompt: str,
    count: int = 5,
    format_type: str = "4cards",
    language: str = "auto",
    channel_profile: str = "",
    episode_context: dict | None = None,
) -> list[dict[str, Any]]:
    """Call CLIProxy API to generate structured Quiz JSON adhering to V2 contract."""
    if channel_profile:
        from app.services.quiz_channel_profiles import get_profile
        language = get_profile(channel_profile)["locale"]
    lang_instruction = (
        "Language: Match user prompt (Vietnamese if written in Vietnamese, English otherwise)."
        if language == "auto"
        else f"Language: Strictly {language}."
    )

    user_instructions = (
        f"Generate exactly {count} quiz questions.\n"
        f"Topic / Requirement: {prompt}\n"
        f"Format preference: {format_type}.\n"
        f"{lang_instruction}\n"
        f"Output MUST be a valid JSON array of questions adhering to specifications with visual prompt descriptions."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_QUIZ_ARCHITECT},
        {"role": "user", "content": user_instructions},
    ]

    if channel_profile:
        from app.services.quiz_channel_profiles import editorial_brief
        messages.append({"role": "user", "content": editorial_brief(channel_profile)})
    context = dict(episode_context or {})
    if context:
        messages.append({"role":"user", "content": "EPISODE REQUIREMENTS: " + json.dumps(context, ensure_ascii=False) +
            "\nFollow the selected series and difficulty, overriding the default progressive curve when specified. "
            "Duration is a target for the WHOLE episode, not this replacement question. Never pad with silence. "
            "Keep persona timer and fact policy. Intro only at question_index=1; outro only at question_total. "
            "Do not repeat other questions. Never invent verified sources."})
    raw_output = _call_cliproxy_llm(messages)
    questions = _parse_and_clean_json(raw_output)

    # Validate contract
    validate_questions(questions, require_assets=False)
    if channel_profile:
        from app.services.quiz_channel_profiles import get_profile
        profile = get_profile(channel_profile)
        for question in questions:
            question.setdefault("countdown_seconds", profile["timer"])
        start = int(context.get('question_index', 1))
        total = int(context.get('question_total', len(questions)))
        for index, question in enumerate(questions, start):
            if context.get('series'):
                question['series'] = context['series']
            if context.get('difficulty_curve') in ('easy','medium','hard'):
                question['difficulty'] = context['difficulty_curve']
            if index == 1:
                question.setdefault('intro_text', profile['hook'])
            else:
                question.pop('intro_text', None)
            if index == total:
                question.setdefault('outro_text', profile['cta'])
            else:
                question.pop('outro_text', None)
    return questions


def enrich_quiz_script_with_prompts(
    questions: list[dict[str, Any]],
    language: str = "auto",
) -> list[dict[str, Any]]:
    """
    Preserve existing user script questions/options/answers, and enrich only missing visual prompts.
    Does NOT modify question text, choices, correct_id, or narration.
    """
    validate_questions(questions, require_assets=False)

    # Prepare lightweight payload of questions needing prompts
    enrichment_targets = []
    for q in questions:
        mode = "4cards" if "cards" in q else ("visual_riddle" if "scene_image" in q or "scene_prompt" in q else "photo_reveal")
        enrichment_targets.append({
            "id": q["id"],
            "mode": mode,
            "question": q["question"],
            "options_or_labels": [c.get("label", "") for c in q.get("cards", [])] if mode == "4cards" else [ch.get("text", "") for ch in q.get("choices", [])],
            "answer": q.get("answer_text") or q.get("correct_option") or q.get("correct_id"),
        })

    prompt = (
        "You are an AI Visual Prompt Artist for Quiz videos.\n"
        "Given the following quiz questions, generate ONLY the visual prompts (image_prompt / scene_prompt / reveal_image_prompt) needed to illustrate them.\n"
        "Return a JSON object mapping question id to its prompt object.\n"
        f"Questions:\n{json.dumps(enrichment_targets, ensure_ascii=False, indent=2)}\n"
        "Return format example: {\"q1\": {\"image_prompts\": [\"prompt 1\", \"prompt 2\", \"prompt 3\", \"prompt 4\"]} or {\"scene_prompt\": \"...\"} or {\"reveal_image_prompt\": \"...\"}}"
    )

    messages = [
        {"role": "system", "content": "You are a visual director. Output strictly valid JSON."},
        {"role": "user", "content": prompt},
    ]

    raw_output = _call_cliproxy_llm(messages)
    clean_text = raw_output.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
        clean_text = re.sub(r"\n?```$", "", clean_text).strip()
    prompts_map = json.loads(clean_text)

    # Merge prompts into original questions without modifying text or answers
    enriched_questions = []
    for q in questions:
        q_copy = dict(q)
        qid = q_copy.get("id")
        p_info = prompts_map.get(qid, {})
        if "cards" in q_copy and "image_prompts" in p_info:
            c_prompts = p_info["image_prompts"]
            for idx, c in enumerate(q_copy["cards"]):
                if idx < len(c_prompts) and not c.get("image_prompt"):
                    c["image_prompt"] = c_prompts[idx]
        elif ("scene_image" in q_copy or "scene_prompt" in q_copy) and "scene_prompt" in p_info:
            if not q_copy.get("scene_prompt"):
                q_copy["scene_prompt"] = p_info["scene_prompt"]
        elif ("choices" in q_copy or "reveal_image_path" in q_copy or "reveal_image_prompt" in q_copy) and "reveal_image_prompt" in p_info:
            if not q_copy.get("reveal_image_prompt"):
                q_copy["reveal_image_prompt"] = p_info["reveal_image_prompt"]

        enriched_questions.append(q_copy)

    validate_questions(enriched_questions, require_assets=False)
    return enriched_questions
