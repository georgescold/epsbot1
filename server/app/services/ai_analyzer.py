import os
import json
import re
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# Global client - will be initialized with API key
client = None
CONFIG_FILE = "config.json"

def get_stored_api_key():
    """Load API key from config file only (user-provided)."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            return config.get("anthropic_api_key", "").strip()
    return ""

def set_api_key(key: str):
    """Update the global client with a new API key."""
    global client
    if key:
        client = Anthropic(api_key=key)
    else:
        client = None

def get_client():
    """Get the Anthropic client, initializing if needed."""
    global client
    if client is None:
        key = get_stored_api_key()
        if key:
            client = Anthropic(api_key=key)
    return client

# Load model from env (default to a fallback if missing, but user requested strict usage)
MODEL_NAME = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

THEMES = [
    "citoyennete", "conceptions", "contexte", "evaluation", 
    "formation_enseignants", "orthodoxie_scolaire", "pratiques_enseignantes",
    "representations_corps", "sciences", "sport_scolaire",
    "textes_institutionnels", "effort", "systeme_scolaire"
]

PERIODS = [
    "1850-1918", "1918-1936", "1936-1944", "1945-1959",
    "1959-1967", "1967-1981", "1981-2007", "2007-today"
]

# Pre-calculate joins to avoid complex expressions inside f-string
themes_str = ', '.join(THEMES)
periods_str = ', '.join(PERIODS)

SYSTEM_PROMPT = f"""
Tu es un expert agrege en EPS de haut niveau. Ta mission est d'analyser des documents (PDFs de recherche, articles, textes officiels) pour en extraire des fiches de revision precises pour le CAPEPS et l'agregation.

REGLE D'OR : EXCLUSIVEMENT BASÉ SUR LE TEXTE.
- Tu ne dois JAMAIS inventer un fait ou une citation. 
- Tout ce que tu extrais doit être présent dans le document fourni.
- Si le document parle d'un auteur, utilise-le. Si le document ne mentionne pas un concept, ne l'ajoute pas de ta propre initiative.

Tu dois identifier des ARGUMENTS et des PREUVES pour les thematiques suivantes : {{themes_str}}.
Pour chaque argument, tu dois le classer dans une periode chronologique precise parmi : {{periods_str}}.

DEFINITIONS DES THEMATIQUES (TRES IMPORTANT -Respecte scrupuleusement le perimetre) :
- citoyennete : évolution de la place de la citoyenneté au sein du système éducatif et de l’EPS.
- conceptions : évolution des conceptions en EPS (courants pédagogiques, visées de l'EPS).
- contexte : évolution du contexte sociétal (éducatif / politique / économique) et ses impacts indirects en EPS.
- evaluation : évolution de l’évaluation en EPS (au niveau de son fond et sa forme / notation / certification).
- formation_enseignants : évolution de la formation des enseignants (initiale et continue, recrutement).
- orthodoxie_scolaire : évolution de l’intégration de l’EPS / reconnaissance de l’EPS au sein du système éducatif (scolarisation de la discipline).
- pratiques_enseignantes : évolution des pratiques enseignantes de terrain en EPS (ce qui se fait réellement dans les gymnases).
- representations_corps : évolution des représentations du corps en EPS et au sein de la société.
- sciences : évolution des sciences et leur impact direct sur l’EPS (physiologie, psychologie, sociologie...).
- sport_scolaire : évolution du sport scolaire (USFSA, OSSU, ASSU, UNSS).
- textes_institutionnels : évolution des textes officiels régissant l’école et l’EPS (Instructions Officielles, Programmes, Lois).
- effort : évolution de la perception et la gestion de l’effort en EPS.
- systeme_scolaire : évolution du système scolaire global (réformes éducatives, massification, démocratisation) et son impact en EPS.

DEFINITIONS :
- Argument : Une tendance generale, une verite constatee a un moment donne, une these demontrable en lien avec la thématique.
- Preuve : Un fait factuel, concret (evenement, texte officiel, statistique) qui appuie l'argument. DOIT TOUJOURS inclure la reference SCIENTIFIQUE (Auteur, Ouvrage/Texte, Annee).
- Complement de preuve : UNE CITATION EXACTE DIFFERENTE de la preuve, tiree du document, pour APPUYER la preuve. Ce n'est PAS une reformulation de la preuve.
- Preuve Nuance : UNE PREUVE SPECIFIQUE qui nuance, critique ou montre les limites de l'argument principal. C'est OBLIGATOIRE pour chaque argument.

REGLES DE REFERENCE STRICTES (CRITIQUE) :
1. Une preuve DOIT s'appuyer sur des travaux scientifiques publies ou des textes officiels.
2. SONT STRICTEMENT INTERDITS (BLACKLIST) - Ne JAMAIS utiliser ces sources :
   - Auteurs bannis : Leroy, Courtois, Ordener, Lorrain.
   - Sources bannies : "Document de formation INSPE", "Cours magistral", "Polycopie", "INSPE de [Ville]", "Support de cours".
   - Si une preuve vient de ces sources, IGNORE-LA.
3. FORMAT ACCEPTE (exemples) :
   - VALIDE : "Cécile Colinet et Philippe Terral, 2021", "Programmes EPS, 2015", "Combaz et Hoibian, 2009".
   - INVALIDE : "Document INSPE Amiens 2020", "Leroy et Courtois", "Cours L2 STAPS".

REGLES D'EXTRACTION :
1. Analyse tout le texte fourni.
2. Extrais les arguments et preuves pertinents en respectant le périmètre strict de chaque thématique definie ci-dessus.
3. Classe-les par thematique et par periode.
4. CHAQUE PREUVE doit contenir : le fait + la reference complete.
5. Le "complement" est OPTIONNEL mais recommande. C'est une citation ADDITIONNELLE.
6. TU DOIS OBLIGATOIREMENT AJOUTER UNE (ET UNE SEULE) "PREUVE NUANCE" POUR CHAQUE ARGUMENT.
7. Les "PREUVES NUANCES" doivent elles aussi etre referencees scientifiquement.
8. QUANTITE : Selectionne MAXIMUM 2 PREUVES "positives" par argument. Si tu en trouves plus, garde seulement les 2 plus pertinentes (plus la nuance).
9. ANTI-DOUBLON (CRITIQUE) :
   - Au sein d'une même THÉMATIQUE et d'une même PÉRIODE : CHAQUE PREUVE DOIT ÊTRE UNIQUE.
   - Interdiction formelle de répéter la même citation pour deux arguments du même thème sur la même époque.
   - Si tu as déjà utilisé une preuve, cherche-en une autre ou n'en mets pas. Favorise la DIVERSITÉ des auteurs.

FORMAT DE SORTIE (JSON uniquement) :
{{
  "analysis": [
    {{
      "theme": "nom_du_theme (ex: citoyennete, systeme_scolaire...)",
      "period": "periode_chronologique",
      "argument": "contenu de l'argument",
      "proofs": [
        {{ 
          "content": "Le fait + (Auteur, Ouvrage/Texte, Annee)", 
          "year": "annee specifique",
          "complement": "Citation exacte entre guillemets (Auteur, Annee) OU null si non disponible",
          "is_nuance": false
        }},
        {{ 
          "content": "La CONTRE-PREUVE ou NUANCE + (Auteur, Ouvrage/Texte, Annee)", 
          "year": "annee specifique",
          "complement": "Citation...",
          "is_nuance": true
        }}
      ]
    }}
  ]
}}
"""

DEFINITION_SYSTEM_PROMPT = """
Tu es un expert agrege en EPS. Ta mission est d'analyser des documents de reference pour en extraire UNIQUEMENT des definitions de concepts et des citations cles.
Ces elements serviront a construire des introductions et des conclusions de dissertation.

EXTRACTION REQUISE :
1. DEFINITIONS : Repere les termes techniques ou concepts cles de l'EPS definis dans le texte.
   - Format : Terme defini + Contenu de la definition precise.
2. CITATIONS : Repere les citations d'auteurs, penseurs, textes officiels qui definissent une idee ou un concept.
   - Format : Auteur/Reference + Contenu de la citation.

FORMAT DE SORTIE (JSON uniquement) :
{
  "extractions": [
    {
      "type": "definition",
      "key_term": "Sport Scolaire",
      "content": "Le sport scolaire se definit comme..."
    },
    {
      "type": "citation",
      "key_term": "Pierre Parlebas, 1981",
      "content": "L'education physique est une pratique d'intervention..."
    }
  ]
}
"""

def clean_json_output(content: str):
    """
    Attempts to clean and extract JSON from AI output.
    Also handles simple truncation cases by closing brackets.
    """
    # Extract JSON block if present
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "{" in content:
        start = content.find("{")
        # If we have a closing brace, use it, otherwise take everything
        end = content.rfind("}") + 1
        if end > start:
            content = content[start:end]
        else:
            content = content[start:]
    
    content = content.strip()
    
    # Attempt to fix truncated JSON (very basic)
    # If it ends with something that looks like it needs closing
    if not content.endswith("}]}") and not content.endswith("]}") and not content.endswith("}"):
        # Check specific common truncation patterns or just append closing chars
        # This is risky but better than failing completely
        if content.endswith("]"):
             content += "}"
        elif content.endswith("}"):
             content += "]}" # Should be covered but being safe
        # Recursive closing is hard, let's try strict loading first
        pass
        
    return content

def analyze_text_chunk(text: str):
    """
    Analyzes a chunk of text using Claude to extract arguments and proofs.
    """
    api_client = get_client()
    if api_client is None:
        print(f"[{datetime.now()}] ERROR: No API key configured!")
        return {"analysis": []}
    
    try:
        message = api_client.messages.create(
            model=MODEL_NAME,
            max_tokens=4000,
            temperature=0,
            system=[
                {
                    "type": "text", 
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": f"Voici le texte à analyser : \n\n{text}"}
            ]
        )
        
        content = message.content[0].text
        cleaned_content = clean_json_output(content)
        
        try:
            return json.loads(cleaned_content)
        except json.JSONDecodeError:
            # Fallback: Try to fix truncated JSON by forcefully closing arrays/objects
            # This is a heuristic attempt
            print("JSON Decode Error - attempting repair")
            # Usually it fails inside the list or object. 
            # We will ignore this chunk if it's too broken, or try a library like 'json_repair' if available
            # Since we can't install packages easily without user approval, we'll return empty for now
            # preventing the crash log.
            # OPTIONAL: Log the error for debug
            print(f"Failed Content: {cleaned_content[-100:]}")
            return {"analysis": []}
            
    except Exception as e:
        print(f"[{datetime.now()}] Error calling AI: {e}")
        return {"analysis": []}

def split_text_into_chunks(text: str, chunk_size: int = 15000):
    """Splits text into chunks of roughly chunk_size characters."""
    return [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]

def analyze_full_text(text: str, progress_callback=None):
    """
    Analyzes the full text by splitting it into chunks and aggregating results.
    Accepts an optional progress_callback(current, total, message)
    """
    chunks = split_text_into_chunks(text)
    aggregated_results = []
    total_chunks = len(chunks)
    print(f"[{datetime.now()}]   -> Splitting into {total_chunks} chunk(s) of ~15k chars")
    
    if progress_callback:
        progress_callback(0, total_chunks, "Starting analysis...")

    for i, chunk in enumerate(chunks):
        print(f"[{datetime.now()}]   -> Processing chunk {i+1}/{total_chunks}...")
        if progress_callback:
            progress_callback(i, total_chunks, f"Processing chunk {i+1}/{total_chunks}")
        
        result = analyze_text_chunk(chunk)
        if result and "analysis" in result:
             aggregated_results.extend(result["analysis"])
        
        if progress_callback:
            progress_callback(i+1, total_chunks, f"Finished chunk {i+1}/{total_chunks}")
             
    return {"analysis": aggregated_results}

def analyze_definition_chunk(text: str):
    """
    Analyzes a chunk of text to extract definitions and citations.
    """
    api_client = get_client()
    if api_client is None: return {"extractions": []}
    
    try:
        message = api_client.messages.create(
            model=MODEL_NAME,
            max_tokens=4000,
            temperature=0,
            system=[
                {
                    "type": "text", 
                    "text": DEFINITION_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {"role": "user", "content": f"Voici le texte de reference a analyser : \n\n{text}"}
            ]
        )
        
        content = message.content[0].text
        cleaned_content = clean_json_output(content)
        return json.loads(cleaned_content)
            
    except Exception as e:
        print(f"[{datetime.now()}] Error calling AI (Def): {e}")
        return {"extractions": []}

def analyze_full_definition_text(text: str):
    """
    Analyzes full text for definitions/citations.
    """
    chunks = split_text_into_chunks(text)
    aggregated_results = []
    
    for chunk in chunks:
        result = analyze_definition_chunk(chunk)
        if result and "extractions" in result:
             aggregated_results.extend(result["extractions"])
             
    return {"extractions": aggregated_results}
