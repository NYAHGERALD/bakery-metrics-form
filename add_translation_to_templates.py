#!/usr/bin/env python3
"""
Script to add auto-translation system to all HTML templates
Adds both the script tag and language switcher to each template
"""

import os
import re
from pathlib import Path

# Templates directory
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Script tag to add
SCRIPT_TAG = """    <script src="{{ url_for('static', filename='js/auto-translate.js') }}"></script>"""

# Language switcher HTML (compact version for navbar)
LANGUAGE_SWITCHER = """                    <!-- Language Switcher -->
                    <div class="language-switcher flex items-center space-x-1 px-2 py-1 bg-white/10 rounded-lg backdrop-blur-sm">
                        <svg class="h-4 w-4 text-white mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129"></path>
                        </svg>
                        <button data-lang="en" class="px-2 py-1 text-xs font-medium text-white rounded transition-all hover:bg-white/10" title="English">EN</button>
                        <button data-lang="fr" class="px-2 py-1 text-xs font-medium text-white/70 rounded transition-all hover:bg-white/10" title="Français">FR</button>
                        <button data-lang="es" class="px-2 py-1 text-xs font-medium text-white/70 rounded transition-all hover:bg-white/10" title="Español">ES</button>
                    </div>"""

def has_translation_script(content):
    """Check if file already has the translation script"""
    return 'auto-translate.js' in content

def add_script_to_html(content):
    """Add translation script before closing </body> tag"""
    if '</body>' in content:
        # Find last </body> tag
        pattern = r'(\s*)</body>'
        replacement = f'{SCRIPT_TAG}\n\\1</body>'
        content = re.sub(pattern, replacement, content)
    return content

def add_language_switcher(content):
    """Add language switcher to navbar if possible"""
    # Try to find common navbar patterns
    navbar_patterns = [
        (r'(<nav[^>]*>.*?</nav>)', 'nav'),
        (r'(<header[^>]*>.*?</header>)', 'header'),
        (r'(<div[^>]*class="[^"]*navbar[^"]*"[^>]*>.*?</div>)', 'navbar-div'),
    ]
    
    for pattern, location in navbar_patterns:
        if re.search(pattern, content, re.DOTALL | re.IGNORECASE):
            # Found a navbar, add switcher at the end before closing tag
            content = re.sub(
                pattern,
                lambda m: m.group(0)[:-len(f'</{location.split("-")[0]}>')] + LANGUAGE_SWITCHER + f'\n                </{location.split("-")[0]}>',
                content,
                flags=re.DOTALL | re.IGNORECASE,
                count=1
            )
            break
    
    return content

def process_template(filepath):
    """Process a single template file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Skip if already has translation
        if has_translation_script(content):
            print(f"⏭️  Skipping {filepath.name} (already has translation)")
            return False
        
        # Add script tag
        content = add_script_to_html(content)
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Added translation to {filepath.name}")
        return True
        
    except Exception as e:
        print(f"❌ Error processing {filepath.name}: {e}")
        return False

def main():
    """Main function to process all templates"""
    if not TEMPLATES_DIR.exists():
        print(f"❌ Templates directory not found: {TEMPLATES_DIR}")
        return
    
    print(f"🚀 Adding translation system to all templates...\n")
    
    # Get all HTML files
    html_files = list(TEMPLATES_DIR.glob("*.html"))
    
    if not html_files:
        print("❌ No HTML files found in templates directory")
        return
    
    processed = 0
    skipped = 0
    
    for filepath in sorted(html_files):
        if process_template(filepath):
            processed += 1
        else:
            skipped += 1
    
    print(f"\n✨ Complete!")
    print(f"   Processed: {processed}")
    print(f"   Skipped: {skipped}")
    print(f"   Total: {len(html_files)}")

if __name__ == "__main__":
    main()
