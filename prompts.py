import pathlib

PROMPT_EN = """You are a warm Danish tutor for beginners (A1-B1). Respond conversationally in English with Danish examples.
Student: {name} | Level: {level} | Today: {today}
Rules: Max 2-3 short sentences. Natural tone. Always end with a question."""

PROMPT_DA = """Du er en venlig dansk sprogunderviser (A1-B1).
Elev: {name} | Niveau: {level} | I dag: {today}
Regler: Max 2-3 korte saetninger. Naturlig tone. Afslut ALTID med sporgsmaal."""

_LANG_PROFILE_DIR = pathlib.Path(__file__).parent / "lang_profiles"


def build_system_prompt(debug: bool, name: str, level: str, today: str, bg_lang: str) -> str:
    base = (PROMPT_EN if debug else PROMPT_DA).format(
        name=name, level=level, today=today)
    profile_path = _LANG_PROFILE_DIR / f"{bg_lang.lower()}.txt"
    try:
        profile = profile_path.read_text(encoding="utf-8")
        return base + f"\n\n## Learner language background ({bg_lang})\n{profile}"
    except FileNotFoundError:
        return base
