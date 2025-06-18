/**
 * Count occurrences of a skill in text
 */
function countOccurrences(text, skill) {
    // Need to escape special regex characters, particularly + in C++
    const escapedSkill = skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`\\b${escapedSkill}\\b`, 'gi');
    const matches = text.match(regex);
    return matches ? matches.length : 0;
}

/**
 * Extract entities from resume text
 */
function extractEntities(text) {
    const entities = {
        name: null,
        email: null,
        phone: null,
        linkedin: null,
        github: null,
        location: null,
        skills: []
    };
    
    // Extract email
    const emailMatch = text.match(EMAIL_PATTERN);
    if (emailMatch) {
        entities.email = emailMatch[0];
    }
    
    // Extract phone
    const phoneMatch = text.match(PHONE_PATTERN);
    if (phoneMatch) {
        entities.phone = phoneMatch[0];
    }
    
    // Extract LinkedIn
    const linkedinMatch = text.match(LINKEDIN_PATTERN);
    if (linkedinMatch) {
        entities.linkedin = linkedinMatch[0];
    }
    
    // Extract GitHub
    const githubMatch = text.match(GITHUB_PATTERN);
    if (githubMatch) {
        entities.github = githubMatch[0];
    }
    
    // Extract name (assume first line of resume is the name)
    const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    if (lines.length > 0 && lines[0].length < 50) {
        // Check if it doesn't contain typical non-name contents
        if (!(/resume|cv|curriculum|@|http|\.com/i.test(lines[0]))) {
            entities.name = lines[0];
        }
    }
    
    // Try to extract location (assume it's in the first few lines, contains a comma)
    for (let i = 0; i < Math.min(5, lines.length); i++) {
        if (lines[i].includes(',') && !/^[^,]+,[^,]+,[^,]+/.test(lines[i])) { // Basic check for address format
            const locationParts = lines[i].split(',').map(part => part.trim());
            if (locationParts.length >= 2) {
                entities.location = lines[i];
                break;
            }
        }
    }
    
    // Extract skills with escaped regex
    for (const skill of COMMON_SKILLS) {
        // Escape special regex characters like + in C++
        const escapedSkill = skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`\\b${escapedSkill}\\b`, 'i');
        if (regex.test(text)) {
            entities.skills.push(skill);
        }
    }
    
    return entities;
}