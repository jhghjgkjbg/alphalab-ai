def ranking_prompt(text: str) -> str:
    return f"Return JSON scores relevance_score, novelty_score, technical_depth, business_value from 0 to 1 for:\n{text}"
