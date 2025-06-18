import spacy
from spacy.matcher import PhraseMatcher

nlp = spacy.load("en_core_web_sm")

def parse_resume(text):
    doc = nlp(text)
    
    skills = ["Python", "Java", "Machine Learning", "Django", "React"]
    matcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp(skill) for skill in skills]
    matcher.add("Skills", None, *patterns)
    
    matches = matcher(doc)
    found_skills = set()
    for match_id, start, end in matches:
        found_skills.add(doc[start:end].text)
    
    return {
        "skills": list(found_skills),
        "experience": len([ent for ent in doc.ents if ent.label_ == "DATE"]),
        "education": [ent.text for ent in doc.ents if ent.label_ == "ORG"]
    }