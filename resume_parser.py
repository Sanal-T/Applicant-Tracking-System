import re
import pandas as pd
from collections import Counter
import language_tool_python

# Initialize language tool for grammar/spelling correction
tool = language_tool_python.LanguageTool('en-US')

class ResumeParser:
    def __init__(self):
        # Define common skills to look for
        self.common_skills = [
            "Python", "Java", "C++", "C#", "JavaScript", "TypeScript", "HTML", "CSS",
            "SQL", "NoSQL", "MongoDB", "PostgreSQL", "MySQL", "Oracle", "SQLite",
            "React", "Angular", "Vue", "Node.js", "Express", "Django", "Flask", "Spring",
            "AWS", "Azure", "Google Cloud", "Docker", "Kubernetes", "Jenkins", "Git",
            "Machine Learning", "Deep Learning", "AI", "Data Science", "Data Analysis",
            "Data Mining", "Data Visualization", "TensorFlow", "PyTorch", "Pandas", "NumPy",
            "Scikit-learn", "Tableau", "Power BI", "Excel", "Word", "PowerPoint", "Outlook",
            "Project Management", "Agile", "Scrum", "Kanban", "Waterfall", "JIRA", "Confluence",
            "Communication", "Leadership", "Teamwork", "Problem Solving", "Critical Thinking",
            "Time Management", "Customer Service", "Sales", "Marketing", "Finance", "Accounting"
        ]
        
        # Regular expressions for entity extraction
        self.email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        self.phone_pattern = r'(\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'
        self.url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        self.linkedin_pattern = r'linkedin\.com/in/[\w\-]+'
        self.github_pattern = r'github\.com/[\w\-]+'
        
        # Section headers (lowercase for comparison)
        self.section_headers = {
            "education": ["education", "academic background", "academic experience", "qualifications"],
            "experience": ["experience", "work history", "employment", "work experience", "professional experience"],
            "skills": ["skills", "technical skills", "core competencies", "competencies"],
            "projects": ["projects", "personal projects", "academic projects", "project experience"],
            "certifications": ["certifications", "certificates", "professional development"],
            "summary": ["summary", "professional summary", "profile", "objective", "about me"]
        }
        
        # Patterns to look for in style checking
        self.personal_pronouns = ["i", "me", "my", "myself"]
        self.passive_patterns = [
            r'\bwas\s+(\w+ed)\b', r'\bwere\s+(\w+ed)\b',
            r'\bis\s+being\s+(\w+ed)\b', r'\bare\s+being\s+(\w+ed)\b',
            r'\bhas\s+been\s+(\w+ed)\b', r'\bhave\s+been\s+(\w+ed)\b',
            r'\bis\s+(\w+ed)\b', r'\bare\s+(\w+ed)\b'
        ]
        self.past_tense_words = [
            r'\b\w+ed\b', r'\bwas\b', r'\bwere\b', r'\bhad\b', 
            r'\bwent\b', r'\bcame\b', r'\bsaid\b', r'\btold\b'
        ]
        self.present_tense_words = [
            r'\bis\b', r'\bare\b', r'\bam\b', r'\bhave\b', r'\bhas\b',
            r'\bcreate\b', r'\bdevelop\b', r'\bmanage\b', r'\blead\b',
            r'\bdesign\b', r'\bimplement\b', r'\bwork\b'
        ]
        
    def parse_resume(self, text):
        """Main function to parse resume text"""
        # Extract entities
        entities = self._extract_entities(text)
        
        # Extract sections
        sections = self._extract_sections(text)
        
        # Check for mistakes
        mistakes = self._check_mistakes(text)
        
        return {
            "entities": entities,
            "sections": sections,
            "mistakes": mistakes
        }
    
    def _extract_entities(self, text):
        """Extract named entities from resume"""
        entities = {
            "name": None,
            "email": None,
            "phone": None,
            "linkedin": None,
            "github": None,
            "skills": [],
            "education": [],
            "experience": []
        }
        
        # Extract email
        email_match = re.search(self.email_pattern, text)
        if email_match:
            entities["email"] = email_match.group()
        
        # Extract phone
        phone_match = re.search(self.phone_pattern, text)
        if phone_match:
            entities["phone"] = phone_match.group()
        
        # Extract LinkedIn
        linkedin_match = re.search(self.linkedin_pattern, text)
        if linkedin_match:
            entities["linkedin"] = linkedin_match.group()
        
        # Extract GitHub
        github_match = re.search(self.github_pattern, text)
        if github_match:
            entities["github"] = github_match.group()
        
        # Extract name (assume first line of resume is the name)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines and len(lines[0]) < 60:  # Reasonable length for a name
            # Check if it doesn't contain typical non-name contents
            if not any(pattern in lines[0].lower() for pattern in 
                      ["resume", "cv", "curriculum", "@", "http", ".com"]):
                entities["name"] = lines[0]
        
        # Extract skills
        for skill in self.common_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', text, re.IGNORECASE):
                entities["skills"].append(skill)
        
        return entities
    
    def _extract_sections(self, text):
        """Identify and extract resume sections"""
        sections = {
            "summary": [],
            "education": [],
            "experience": [],
            "skills": [],
            "projects": [],
            "certifications": []
        }
        
        # Split text into lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        current_section = None
        section_content = []
        
        for i, line in enumerate(lines):
            # Check if this line is a section header
            found_section = None
            for section, headers in self.section_headers.items():
                if any(header == line.lower() for header in headers):
                    found_section = section
                    break
            
            # If we found a new section header
            if found_section:
                # Save content from previous section
                if current_section and section_content:
                    sections[current_section] = section_content
                
                # Start new section
                current_section = found_section
                section_content = []
            
            # Add content to current section
            elif current_section:
                section_content.append(line)
            
            # If it's the last line, save the current section content
            if i == len(lines) - 1 and current_section and section_content:
                sections[current_section] = section_content
        
        return sections
    
    def _check_mistakes(self, text):
        """Check for spelling/grammar mistakes and formatting issues"""
        mistakes = []
        
        # Check spelling/grammar
        matches = tool.check(text)
        for match in matches:
            if match.ruleIssueType not in ["typographical", "grammar"]:
                continue
            mistakes.append({
                "type": match.ruleIssueType,
                "message": match.message,
                "context": match.context,
                "suggestion": match.replacements[0] if match.replacements else "",
                "offset": match.offset,
                "length": match.errorLength
            })
        
        # Check for common resume issues
        
        # Simple sentence tokenization using regex
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # 1. Check for personal pronouns (I, me, my)
        for sentence in sentences:
            words = re.findall(r'\b\w+\b', sentence.lower())
            if any(word in self.personal_pronouns for word in words):
                mistakes.append({
                    "type": "style",
                    "message": "Personal pronoun detected in resume",
                    "context": sentence,
                    "suggestion": "Avoid using personal pronouns in resumes"
                })
                break
        
        # 2. Check for passive voice (simple regex patterns)
        for pattern in self.passive_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Find the sentence containing this pattern
                for sentence in sentences:
                    if match.group() in sentence:
                        mistakes.append({
                            "type": "style",
                            "message": "Passive voice detected",
                            "context": sentence,
                            "suggestion": "Consider rewriting in active voice"
                        })
                        break
                break
        
        # 3. Check for inconsistent verb tenses
        past_tense_count = 0
        present_tense_count = 0
        
        # Count past tense verbs
        for pattern in self.past_tense_words:
            matches = re.findall(pattern, text, re.IGNORECASE)
            past_tense_count += len(matches)
        
        # Count present tense verbs
        for pattern in self.present_tense_words:
            matches = re.findall(pattern, text, re.IGNORECASE)
            present_tense_count += len(matches)
        
        # If there's a significant mix of tenses
        if past_tense_count > 3 and present_tense_count > 3:
            mistakes.append({
                "type": "style",
                "message": "Inconsistent verb tenses detected",
                "suggestion": "Use consistent verb tenses (all past or all present)"
            })
        
        return mistakes
    
    def generate_corrected_text(self, text):
        """Generate corrected version of the text"""
        corrected = tool.correct(text)
        return corrected
    
    def analyze_resume_quality(self, parsed_result):
        """Analyze the overall quality of the resume"""
        quality_score = 0
        feedback = []
        
        # 1. Check if essential contact information is present
        entities = parsed_result["entities"]
        
        if not entities["email"]:
            feedback.append("Missing email address")
        else:
            quality_score += 10
            
        if not entities["phone"]:
            feedback.append("Missing phone number")
        else:
            quality_score += 10
            
        # 2. Check if skills are present
        if not entities["skills"]:
            feedback.append("No skills detected")
        else:
            # More skills = better (up to a point)
            skill_count = len(entities["skills"])
            if skill_count > 15:
                quality_score += 20
                feedback.append("Excellent range of skills listed")
            elif skill_count > 10:
                quality_score += 15
                feedback.append("Good range of skills listed")
            elif skill_count > 5:
                quality_score += 10
                feedback.append("Moderate range of skills listed")
            else:
                quality_score += 5
                feedback.append("Consider adding more skills")
                
        # 3. Check for education and experience sections
        sections = parsed_result["sections"]
        
        if not sections["education"]:
            feedback.append("Missing education section")
        else:
            # Basic check for education section length
            if len('\n'.join(sections["education"])) > 100:
                quality_score += 15
            else:
                quality_score += 5
                feedback.append("Education section could be more detailed")
                
        if not sections["experience"]:
            feedback.append("Missing work experience section")
        else:
            # Basic check for experience section length
            if len('\n'.join(sections["experience"])) > 200:
                quality_score += 25
            else:
                quality_score += 10
                feedback.append("Work experience section could be more detailed")
                
        # 4. Check for mistakes
        mistakes = parsed_result["mistakes"]
        
        # Deduct points for mistakes
        quality_score -= min(20, len(mistakes) * 2)
        
        if len(mistakes) > 10:
            feedback.append("Numerous grammar/spelling issues detected")
        elif len(mistakes) > 5:
            feedback.append("Several grammar/spelling issues detected")
        elif len(mistakes) > 0:
            feedback.append("Minor grammar/spelling issues detected")
        else:
            feedback.append("No grammar/spelling issues detected")
            quality_score += 10
            
        # 5. Check if there are projects listed
        if sections["projects"]:
            quality_score += 10
            feedback.append("Good inclusion of projects")
            
        # 6. Check for a summary section
        if sections["summary"]:
            quality_score += 10
            feedback.append("Good inclusion of a summary/objective")
        else:
            feedback.append("Consider adding a professional summary")
            
        # Ensure quality score is between 0 and 100
        quality_score = max(0, min(100, quality_score))
        
        return {
            "score": quality_score,
            "feedback": feedback,
            "rating": "Excellent" if quality_score >= 90 else
                     "Very Good" if quality_score >= 80 else
                     "Good" if quality_score >= 70 else
                     "Fair" if quality_score >= 50 else
                     "Needs Improvement"
        }


# Example usage
if __name__ == "__main__":
    parser = ResumeParser()
    
    sample_resume = """
    John Doe
    123 Main St, Anytown, USA
    (123) 456-7890 | john.doe@email.com
    
    EDUCATION
    Bachelor of Science in Computer Science
    University of Example, 2015-2019
    GPA: 3.8
    
    SKILLS
    Python, Java, SQL, Data Analysis
    
    EXPERIENCE
    Software Engineer
    ABC Corp, 2019-Present
    - Develop web applications using Python
    - Collaborate with team members
    - I was responsible for database design
    
    PROJECTS
    Resume Parser Application
    - Created a Python application to parse resumes
    - Used NLP techniques for entity recognition
    """
    
    print("Parsing resume...")
    result = parser.parse_resume(sample_resume)
    
    print("\nExtracted Entities:")
    for entity_type, value in result["entities"].items():
        if isinstance(value, list):
            print(f"{entity_type.capitalize()}: {', '.join(value) if value else 'None'}")
        else:
            print(f"{entity_type.capitalize()}: {value if value else 'None'}")
    
    print("\nExtracted Sections:")
    for section_type, content in result["sections"].items():
        if content:
            print(f"\n{section_type.upper()}:")
            for line in content:
                print(f"- {line}")
    
    print("\nMistakes Found:")
    for mistake in result["mistakes"]:
        print(f"- {mistake['type'].upper()}: {mistake['message']}")
        if 'context' in mistake and mistake['context']:
            print(f"  Context: {mistake['context']}")
        print(f"  Suggestion: {mistake.get('suggestion', '')}")
    
    analysis = parser.analyze_resume_quality(result)
    print(f"\nResume Quality Score: {analysis['score']}/100 ({analysis['rating']})")
    print("Feedback:")
    for item in analysis['feedback']:
        print(f"- {item}")
    
    print("\nCorrected Resume Text:")
    corrected = parser.generate_corrected_text(sample_resume)
    print(corrected) 