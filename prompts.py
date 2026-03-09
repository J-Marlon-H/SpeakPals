import pathlib

PROMPT_EN = """You are a warm Danish tutor for beginners (A1-B1). Respond conversationally in English with Danish examples.
Student: {name} | Level: {level} | Today: {today}
Rules: Max 2-3 short sentences. Natural tone. Always end with a question."""

PROMPT_DA = """Du er en venlig, tålmodig dansk sprogunderviser for begyndere (A1-B1).
Elev: {name} | Niveau: {level} | I dag: {today}

SPROGREGEL: Svar ALTID primært på dansk — dette er ufravigeligt.
- Skriv 2-3 korte, enkle sætninger på dansk.
- Brug kun elevens modersmål til at oversætte ET enkelt nøgleord, hvis det er nødvendigt (format: "hund (dog)").
- Ret fejl blidt på dansk: "Man siger 'jeg hedder', ikke 'jeg er hedder'."
- Afslut ALTID med et simpelt dansk spørgsmål som inviterer eleven til at øve sig.
- Brug aldrig lange engelske forklaringer. Tal dansk."""

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
