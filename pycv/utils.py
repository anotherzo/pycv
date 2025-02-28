def sanitize_text_for_latex(text: str) -> str:
    """
    Sanitize text for LaTeX by escaping special characters.
    
    Args:
        text: The input text to sanitize
        
    Returns:
        Sanitized text safe for LaTeX
    """
    if not isinstance(text, str):
        return text
        
    # Characters that need escaping in LaTeX
    replacements = {
        '_': r'\_',
        '%': r'\%',
        '&': r'\&',
        '#': r'\#',
        '$': r'\$',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}'
    }
    
    # Apply all replacements
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
        
    return text
