"""
Flashcard Generation Service
Optimized for comprehensive coverage with Anki-style cards.
"""

import json
from datetime import datetime
from .ai_analyzer import get_client, clean_json_output

# Use Sonnet for better quality flashcard generation
# Claude 3.5 Haiku : meilleur compromis qualité/coût pour génération structurée
FLASHCARD_MODEL = "claude-3-5-haiku-20241022"

FLASHCARD_SYSTEM_PROMPT = """Tu es un expert agrégé en EPS et en création de flashcards Anki optimisées pour la mémorisation à long terme.

MISSION : Transformer un ARGUMENT d'histoire de l'EPS et ses PREUVES en flashcards exhaustives et efficaces.

=== PRINCIPES FONDAMENTAUX ===

1. CONCISION : Maximum 3 cartes par argument
   - Sélectionner les informations les plus cruciales
   - Prioriser ce qui est essentiel pour l'examen

2. ATOMICITÉ : Une seule information par carte
   - Chaque flashcard teste UN SEUL élément de connaissance
   - Questions courtes et précises

3. ÉVITER LES DOUBLONS : Pas de questions redondantes
   - Chaque carte doit apporter une information unique

=== 3 CARTES À CRÉER (dans cet ordre de priorité) ===

1. CARTE CONCEPT : L'idée générale de l'argument
   - Quelle est la tendance/vérité générale ?

2. CARTE PREUVE : La preuve principale avec auteur et date
   - Qui ? Quand ? Quel fait précis ?

3. CARTE NUANCE : La limite ou le contre-argument
   - Quelle nuance ? Quel auteur contredit ?

=== FORMAT ===

Questions courtes et directes :
- "Quelle est l'idée principale concernant [X] ?"
- "Quel auteur/quelle preuve illustre [X] ?"
- "Quelle nuance apporter à [X] ?"

Réponses concises :
- Auteur + date + fait essentiel
- Maximum 2-3 phrases

=== FORMAT DE SORTIE ===

Retourner UNIQUEMENT un JSON valide :
{
  "flashcards": [
    {
      "front": "Question claire et précise",
      "back": "Réponse concise avec auteur/date si pertinent"
    }
  ]
}

IMPORTANT :
- Générer EXACTEMENT 3 flashcards maximum par argument
- Prioriser : 1 carte concept principal, 1 carte preuve/auteur clé, 1 carte nuance
- Choisir les informations les plus essentielles à retenir"""


def generate_flashcards_from_argument(theme: str, period: str, argument_content: str, proofs_text: str):
    """
    Generates comprehensive flashcards for a specific argument context.

    Args:
        theme: The theme (e.g., "citoyennete", "conceptions")
        period: The chronological period (e.g., "1850-1918")
        argument_content: The main argument content
        proofs_text: Formatted proofs and nuances

    Returns:
        List of flashcard dictionaries with 'front' and 'back' keys
    """
    client = get_client()
    if not client:
        return []

    # Construct detailed context
    context = f"""
=== CONTEXTE ===
THÉMATIQUE : {theme}
PÉRIODE : {period}

=== ARGUMENT PRINCIPAL ===
{argument_content}

=== PREUVES ET NUANCES ===
{proofs_text}

=== INSTRUCTIONS ===
Génère EXACTEMENT 3 flashcards :
1. Une carte sur l'idée générale de l'argument
2. Une carte sur la preuve principale (auteur, date, fait)
3. Une carte sur la nuance principale (si disponible, sinon une autre preuve clé)
"""

    try:
        message = client.messages.create(
            model=FLASHCARD_MODEL,
            max_tokens=4000,
            temperature=0.3,  # Slight creativity for varied formulations
            system=FLASHCARD_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": context}
            ]
        )

        content = message.content[0].text
        cleaned = clean_json_output(content)
        data = json.loads(cleaned)

        flashcards = data.get("flashcards", [])

        # Validation: ensure each card has front and back
        validated = []
        seen_fronts = set()

        for card in flashcards:
            front = card.get("front", "").strip()
            back = card.get("back", "").strip()

            if front and back and front not in seen_fronts:
                validated.append({"front": front, "back": back})
                seen_fronts.add(front)

        return validated

    except json.JSONDecodeError as e:
        print(f"[{datetime.now()}] JSON parsing error in flashcard generation: {e}")
        return []
    except Exception as e:
        print(f"[{datetime.now()}] Flashcard generation error: {e}")
        return []


def generate_flashcards_batch(arguments_data: list):
    """
    Generate flashcards for multiple arguments efficiently.

    Args:
        arguments_data: List of dicts with keys: theme, period, content, proofs_text

    Returns:
        Dict mapping argument index to list of flashcards
    """
    results = {}

    for i, arg in enumerate(arguments_data):
        cards = generate_flashcards_from_argument(
            theme=arg.get("theme", ""),
            period=arg.get("period", ""),
            argument_content=arg.get("content", ""),
            proofs_text=arg.get("proofs_text", "")
        )
        results[i] = cards

    return results
