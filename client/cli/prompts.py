def prompt_text(label: str, default: str = "", required: bool = True) -> str:
    """Prompts for text input, showing default if provided."""
    while True:
        prompt_str = f"{label} [{default}]: " if default else f"{label}: "
        val = input(prompt_str).strip()
        
        if not val and default:
            return default
            
        if not val and required:
            print(f"⚠️  \033[33m{label} is required.\033[0m")
            continue
            
        return val

def prompt_yes_no(label: str, default: str = "N") -> bool:
    """Prompts for a yes/no answer."""
    prompt_str = f"{label} (y/n) [{default}]: "
    val = input(prompt_str).strip().lower()
    
    if not val:
        val = default.lower()
        
    return val == 'y'
