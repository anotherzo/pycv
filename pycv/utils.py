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
    # Order matters - backslash must be first to avoid double-escaping
    replacements = [
        ('\\', r'\textbackslash{}'),
        ('_', r'\_'),
        ('%', r'\%'),
        ('&', r'\&'),
        ('#', r'\#'),
        ('$', r'\$'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
        ('<', r'\textless{}'),
        ('>', r'\textgreater{}')
    ]
    
    # Apply all replacements in order
    for char, replacement in replacements:
        text = text.replace(char, replacement)
    
    # Handle paragraph breaks properly for LaTeX
    # Replace double newlines with LaTeX paragraph breaks
    text = text.replace('\n\n', '\n\\par\n')
        
    return text
