/**
 * Extract skills from the resume
 * @param {string} text - Full resume text
 * @param {Object} sections - Identified sections
 * @returns {Array} Array of identified skills
 */
function extractSkills(text, sections) {
    const skills = new Set();
    
    // First, check for common skills throughout the text
    for (const skill of COMMON_SKILLS) {
        // Escape special regex characters like + in C++
        const escapedSkill = skill.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        if (new RegExp(`\\b${escapedSkill}\\b`, 'i').test(text)) {
            skills.add(skill);
        }
    }
    
    // Then, if there's a skills section, focus on that
    if (sections.skills) {
        const { start, end } = sections.skills;
        const skillsText = text.split('\n').slice(start, end + 1).join(' ');
        
        // Look for comma or bullet separated lists
        const skillsList = skillsText.split(/[,•|\/\-]/).map(s => s.trim());
        
        for (const skillItem of skillsList) {
            if (skillItem.length > 2 && skillItem.length < 30) {
                skills.add(skillItem);
            }
        }
    }
    
    return Array.from(skills);
}