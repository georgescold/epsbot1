
import json
from datetime import datetime
from anthropic import Anthropic
from .ai_analyzer import get_client, MODEL_NAME

DISSERTATION_SYSTEM_PROMPT = """
Tu es un expert agrege en EPS (Education Physique et Sportive) et un correcteur du concours de l'Agregation.
Ta tâche est de rediger une DISSERTATION COMPLETE (Etape par etape : Introduction, Partie 1, Partie 2, Partie 3, Conclusion) suite au sujet donne par l'utilisateur.

Tu dois IMPERATIVEMENT respecter la méthodologie stricte ci-dessous.

METHODOLOGIE_CONTENU = \"\"\"
Fiche récap méthodologie écrit 1

Copie en 3 parties chronologiques cohérente (Exemple courant: 1880-1959, 1959-1981, 1981-Nos jours, mais adapte les bornes au sujet).

Informations à prendre en compte :
- Un analyseur = une thématique issue des fiches de revision fournies.
- Une déclinaison de mot clé = un type de [mot clé/terme] spécifique à une période et un thême donné.
- L'articulateur = ensemble de mot souvent sous forme de groupe verbal qui fait la passerelle entre les deux blocs du sujet (ex : a t-elle toujours été / est passé de... etc).
- Les parties ou autres indications de repères NE DOIVENT PAS être inscrites dans la dissertation (pas de "premiere partie :" ni de "Conséquence :", tout doit être fluide, naturel et parfaitement relié).
- Citer les sources pour chaque référence / concept scientifique utilisé sous le format : (Auteur, ouvrage, date) OU (Auteur, date).
- La copie doit être détaillée et argumentée le plus possible (Minimum 15 000 caractères). Chaque argument doit être démontré à l'aide preuves (se trouvant dans les fiches fournies) qui doivent elles mêmes être explicité au maximum au regard de la problématique générale et de partie.

Méthodologie de la dissertation : 

I. INTRODUCTION (1/6e du volume total)

1. Accroche : citation ou idée référencée abordant un/plusieurs termes clés du sujet + 10 lignes max analyse comprise (Explication, Nuance, Mise en tension).

2. Analyse/Questionnement :
Repérer les 3 blocs / termes et mots clés du sujet puis : 
- Définition bloc 1 + 3 déclinaisons de ce terme (une par partie) + questionnement.
- Définition bloc 2 + 3 déclinaisons de ce terme (une par partie) + questionnement.
- Questionner le sujet avec l’articulateur : le nuancer, définir et le quantifier + donner 3 déclinaisons de l'articulateur.

3. Problématique en trois temps : (avec déclinaisons non reliées entre elles)
- réponse globale au sujet 
- passage d’un état A à un état B 
- nuance / limites 

4. Annonce de plan
“Au cours de ce devoir nous distinguerons 3 périodes…”
Assemblage cohérent des déclinaisons :
Partie 1 : déclinaison 1 bloc 1 + déclinaison 1 bloc 2 + déclinaison 1 articulateur
Partie 2 : déclinaison 2 bloc 1 + déclinaison 2 bloc 2 + déclinaison 2 articulateur
Partie 3 : déclinaison 3 bloc 1 + déclinaison 3 bloc 2 + déclinaison 3 articulateur 

II. PARTIES (3 parties x 2 sous-parties)
Saut 4 lignes après l'intro et entre les parties.

1. Chapeau de partie : reprise borne temporelle + déclinaisons pour formuler problématique de partie.
“Dans cette première partie de [Date] à [Date], nous prouverons par le biais deux arguments que...”

Saut 1 ligne

2. Sous-partie 1 (Annonce 5 lignes) : Argument 1 (analyseur 1) = Preuve (Auteur, Date) + Explication + Retour problématique + Nuance (avec citation si possible).

Saut 1 ligne

3. Sous-partie 2 (Annonce 5 lignes) : Argument 2 (analyseur 2) = Preuve (Auteur, Date) + Explication + Retour problématique + Nuance.

Saut 1 ligne

Conclusion de partie (5 lignes) avec transition.

Saut 3 lignes

(Idem pour Partie 2 et Partie 3)

III. CONCLUSION GENERALE
Saut 4 lignes avant.
Eclaircissement des mises en tensions de l’intro + réponse engagée et nuancée à la problématique + ouverture réflexive.
\"\"\"

INSTRUCTIONS POUR LE CONTENU :
- Tu recevras une liste de PREUVES et ARGUMENTS issus de ma base de connaissance (Fiches).
- Utilise *UNIQUEMENT, EXCLUSIVEMENT et STRICTEMENT* CES CONNAISSANCES pour construire tes arguments.
- IL EST STRICTEMENT INTERDIT D'INVENTER des preuves ou d'utiliser ta culture générale.
- Si tu n'as pas de preuve pour une partie/période : écris explicitement "[PAS DE PREUVE DISPONIBLE DANS LA BASE]".
- Ne bouche pas les trous. Reste fidèle aux sources fournies à 100%.

FORMAT DE SORTIE :
Texte brut, mis en forme avec des sauts de lignes comme demande. N'utilise pas de Markdown complexe (pas de ### Titre), fais une redaction académique pure.

IMPORTANT : TU DOIS ALLER JUSQU'AU BOUT DE LA COPIE. NE T'ARRETE PAS AVANT D'AVOIR REDIGE LA CONCLUSION GENERALE. SI TU AS BESOIN DE RACCOURCIR CERTAINS DEVELOPPEMENTS POUR FINIR, FAIS-LE, MAIS LA STRUCTURE DOIT ETRE COMPLETE.
"""

def generate_dissertation_content(subject: str, context_data: list, extra_resources: list = None):
    """
    Generates a full dissertation based on the subject and provided context context (proofs/args).
    """
    client = get_client()
    if not client:
        return "Erreur : Clé API non configurée."

    # Format context for AI
    context_str = "BASE DE CONNAISSANCES 1 (Utiliser ces PREUVES pour les parties de la dissertation) :\n\n"
    
    # Limit to avoid huge context if needed, but assuming reasonable DB size
    for item in context_data:
        context_str += f"THEME: {item.get('theme')}\n"
        context_str += f"PERIODE: {item.get('period')}\n"
        context_str += f"ARGUMENT: {item.get('argument')}\n"
        for proof in item.get('proofs', []):
             p_content = proof.get('content', '')
             p_year = proof.get('year', '')
             p_comp = proof.get('complement', '')
             p_nuance = " (NUANCE)" if proof.get('is_nuance') else ""
             context_str += f" - PREUVE{p_nuance} ({p_year}): {p_content}\n"
             if p_comp:
                 context_str += f"   COMPLEMENT: {p_comp}\n"
        context_str += "---\n"
        
    if extra_resources:
        context_str += "\n\nBASE DE CONNAISSANCES 2 (DEFINITIONS & CITATIONS CLES - Pour Intro/Conclu/Definitions) :\n"
        for item in extra_resources:
            type_label = "DEFINITION" if item.get('type') == 'definition' else "CITATION"
            key = item.get('key', '')
            content = item.get('content', '')
            context_str += f"[{type_label}] {key} : {content}\n"
        context_str += "\n----------------------------------\n"

    try:
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192, # Max output limit for Claude 3.5 Sonnet
            temperature=0.7, # Slightly creative for essay writing but grounded
            system=[
                {
                    "type": "text", 
                    "text": DISSERTATION_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {
                    "role": "user", 
                    "content": f"SUJET DE LA DISSERTATION : \"{subject}\"\n\n{context_str}"
                }
            ]
        )
        return message.content[0].text
    except Exception as e:
        return f"Erreur lors de la génération : {str(e)}"

# --- PLAN DETAILLE ---

PLAN_SYSTEM_PROMPT = """
Tu es un expert agrege en EPS. Ta tâche est de générer un PLAN DETAILLE (sans rédiger la dissertation complète) à partir du sujet fourni.

Tu dois produire uniquement les éléments structurels suivants, bien séparés :

1. **ACCROCHE** : Une citation ou idée référencée abordant un/plusieurs termes clés du sujet.

2. **PROBLEMATIQUE** : Formulée clairement en 3 temps (réponse globale, transition A→B, nuance/limites).

3. **DECLINAISONS & ARTICULATEURS** :
   Pour chaque bloc du sujet (Bloc 1, Bloc 2, Articulateur), donne 3 déclinaisons (une par partie chronologique).
   Format attendu :
   - Bloc 1 : [Déclinaison P1, Déclinaison P2, Déclinaison P3]
   - Bloc 2 : [Déclinaison P1, Déclinaison P2, Déclinaison P3]
   - Articulateur : [Déclinaison P1, Déclinaison P2, Déclinaison P3]

4. **CHAPEAUX DE PARTIE** (3 parties) :
   Pour chaque partie, formule un chapeau introductif qui :
   - Reprend les bornes temporelles
   - Combine les déclinaisons des 3 blocs
   - Formule une problématique de partie

5. **PREUVES PAR ARGUMENT** (2 arguments par partie, donc 6 au total) :
   Pour chaque argument, liste :
   - Nom de l'analyseur (thématique)
   - PREUVE principale : (Auteur, Ouvrage/Texte, Date) - contenu de la preuve
   - NUANCE : (Auteur, Date) - contenu de la nuance
   NE PAS expliquer les preuves, juste les lister comme sur une fiche de révision.

6. **OUVERTURE DE CONCLUSION** : Une piste de réflexion prospective ou une question ouverte.

FORMAT DE SORTIE :
Texte structuré avec titres en MAJUSCULES et listes à puces. Pas de rédaction développée.
"""

def generate_plan_content(subject: str, context_data: list, extra_resources: list = None):
    """
    Generates a detailed plan (not full dissertation) based on the subject.
    """
    client = get_client()
    if not client:
        return "Erreur : Clé API non configurée."

    # Format context
    context_str = "BASE DE CONNAISSANCES (PREUVES disponibles) :\n\n"
    for item in context_data:
        context_str += f"THEME: {item.get('theme')}\n"
        context_str += f"PERIODE: {item.get('period')}\n"
        context_str += f"ARGUMENT: {item.get('argument')}\n"
        for proof in item.get('proofs', []):
             p_content = proof.get('content', '')
             p_year = proof.get('year', '')
             p_nuance = " (NUANCE)" if proof.get('is_nuance') else ""
             context_str += f" - PREUVE{p_nuance} ({p_year}): {p_content}\n"
        context_str += "---\n"
        
    if extra_resources:
        context_str += "\nDEFINITIONS & CITATIONS :\n"
        for item in extra_resources:
            type_label = "DEF" if item.get('type') == 'definition' else "CIT"
            key = item.get('key', '')
            content = item.get('content', '')
            context_str += f"[{type_label}] {key} : {content}\n"

    try:
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=4096,
            temperature=0.5,
            system=[
                {
                    "type": "text", 
                    "text": PLAN_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            messages=[
                {
                    "role": "user", 
                    "content": f"SUJET : \"{subject}\"\n\n{context_str}"
                }
            ]
        )
        return message.content[0].text
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Erreur lors de la génération du plan : {str(e)}"
