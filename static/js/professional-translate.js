/**
 * Professional Auto-Translation System for DASHMET
 * Automatically translates all page content without manual dictionary
 * Supports: English (EN), Español (ES)
 * Brand name "DASHMET" is never translated
 */

class ProfessionalTranslate {
    constructor() {
        this.currentLang = localStorage.getItem('app_language') || 'en';
        this.translationCache = JSON.parse(localStorage.getItem('translation_cache') || '{}');
        this.isTranslating = false;
        this.translatedElements = new WeakSet();
    }
    
    // Translate text using LibreTranslate API (free, no key required)
    async translateText(text, targetLang = 'es') {
        if (!text || typeof text !== 'string') return text;
        
        const trimmed = text.trim();
        
        // Never translate DASHMET, numbers, or very short text
        if (trimmed === 'DASHMET' || 
            trimmed.includes('DASHMET') || 
            trimmed.length < 2 ||
            /^[\d\s\-\/:.%,]+$/.test(trimmed)) {
            return text;
        }
        
        // Check cache first
        const cacheKey = `${targetLang}:${trimmed}`;
        if (this.translationCache[cacheKey]) {
            return this.translationCache[cacheKey];
        }
        
        // Use MyMemory Translation API (free, unlimited for reasonable use)
        try {
            const url = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(trimmed)}&langpair=en|${targetLang}`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.responseStatus === 200 && data.responseData.translatedText) {
                const translated = data.responseData.translatedText;
                
                // Cache the translation
                this.translationCache[cacheKey] = translated;
                this.saveCacheToStorage();
                
                return translated;
            }
        } catch (error) {
            console.warn('Translation API error:', error);
        }
        
        // Return original if API fails
        return text;
    }
    
    // Save cache to localStorage (limit to 1000 entries)
    saveCacheToStorage() {
        try {
            const entries = Object.entries(this.translationCache);
            if (entries.length > 1000) {
                // Keep only the most recent 1000 entries
                this.translationCache = Object.fromEntries(entries.slice(-1000));
            }
            localStorage.setItem('translation_cache', JSON.stringify(this.translationCache));
        } catch (e) {
            console.warn('Could not save translation cache');
        }
    }
    
    // Check if element should be translated
    shouldTranslate(element) {
        // Skip if already translated
        if (this.translatedElements.has(element)) {
            return false;
        }
        
        // Skip if has no-translate attribute
        if (element.hasAttribute('data-no-translate') || element.closest('[data-no-translate]')) {
            return false;
        }
        
        // Skip script, style, etc
        const skipTags = ['SCRIPT', 'STYLE', 'CODE', 'PRE', 'NOSCRIPT'];
        if (skipTags.includes(element.tagName)) {
            return false;
        }
        
        return true;
    }
    
    // Translate a single element
    async translateElement(element) {
        if (!this.shouldTranslate(element) || this.currentLang === 'en') {
            return;
        }
        
        // Mark as translated
        this.translatedElements.add(element);
        
        // Translate direct text nodes only
        for (let node of element.childNodes) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                if (text && text.length > 0) {
                    const before = node.textContent.match(/^\s*/)[0];
                    const after = node.textContent.match(/\s*$/)[0];
                    
                    const translated = await this.translateText(text, this.currentLang);
                    if (translated !== text) {
                        node.textContent = before + translated + after;
                    }
                }
            }
        }
        
        // Translate attributes
        if (element.hasAttribute('placeholder')) {
            const placeholder = element.getAttribute('placeholder');
            const translated = await this.translateText(placeholder, this.currentLang);
            element.setAttribute('placeholder', translated);
        }
        
        if (element.hasAttribute('aria-label')) {
            const ariaLabel = element.getAttribute('aria-label');
            const translated = await this.translateText(ariaLabel, this.currentLang);
            element.setAttribute('aria-label', translated);
        }
        
        if (element.hasAttribute('title')) {
            const title = element.getAttribute('title');
            const translated = await this.translateText(title, this.currentLang);
            element.setAttribute('title', translated);
        }
    }
    
    // Translate entire page
    async translatePage() {
        if (this.currentLang === 'en' || this.isTranslating) {
            return;
        }
        
        this.isTranslating = true;
        
        // Show loading indicator
        this.showTranslatingIndicator();
        
        try {
            // Get all translatable elements
            const selectors = 'h1, h2, h3, h4, h5, h6, p, span:not(:empty), a, button, label, td, th, li, div, option';
            const elements = Array.from(document.querySelectorAll(selectors));
            
            // Filter to only elements with direct text content
            const translatableElements = elements.filter(el => {
                if (!this.shouldTranslate(el)) return false;
                return Array.from(el.childNodes).some(node => 
                    node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0
                );
            });
            
            // Translate in batches to avoid overwhelming the API
            const batchSize = 20;
            for (let i = 0; i < translatableElements.length; i += batchSize) {
                const batch = translatableElements.slice(i, i + batchSize);
                await Promise.all(batch.map(el => this.translateElement(el)));
                
                // Small delay to avoid rate limiting
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            // Translate inputs and textareas
            const inputs = document.querySelectorAll('input[placeholder], textarea[placeholder]');
            for (const input of inputs) {
                if (input.placeholder) {
                    input.placeholder = await this.translateText(input.placeholder, this.currentLang);
                }
            }
        } catch (error) {
            console.error('Translation error:', error);
        } finally {
            this.isTranslating = false;
            this.hideTranslatingIndicator();
        }
    }
    
    // Show translating indicator
    showTranslatingIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'translation-indicator';
        indicator.className = 'fixed top-20 right-5 bg-blue-500 text-white px-4 py-2 rounded-lg shadow-lg z-[9999] flex items-center gap-2';
        indicator.innerHTML = `
            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Translating...</span>
        `;
        document.body.appendChild(indicator);
    }
    
    // Hide translating indicator
    hideTranslatingIndicator() {
        const indicator = document.getElementById('translation-indicator');
        if (indicator) {
            indicator.remove();
        }
    }
    
    // Change language
    async setLanguage(lang) {
        if (lang === this.currentLang) return;
        
        this.currentLang = lang;
        localStorage.setItem('app_language', lang);
        
        // Reload page for clean translation
        window.location.reload();
    }
    
    // Update language switcher UI
    updateLanguageSwitcher() {
        const currentLangSpan = document.getElementById('currentLang');
        if (currentLangSpan) {
            currentLangSpan.textContent = this.currentLang === 'en' ? 'English' : 'Español';
        }
        
        // Update dropdown menu checkmarks
        document.querySelectorAll('.lang-option').forEach(btn => {
            const lang = btn.getAttribute('data-lang');
            const checkIcon = btn.querySelector('.check-icon');
            if (lang === this.currentLang) {
                checkIcon?.classList.remove('hidden');
                btn.classList.add('bg-blue-50');
            } else {
                checkIcon?.classList.add('hidden');
                btn.classList.remove('bg-blue-50');
            }
        });
        
        // Update mobile select
        const mobileSelect = document.getElementById('mobileLangSelect');
        if (mobileSelect) {
            mobileSelect.value = this.currentLang;
        }
    }
    
    // Watch for dynamic content
    observeDOM() {
        const observer = new MutationObserver(mutations => {
            if (this.currentLang === 'en') return;
            
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        this.translateElement(node);
                        node.querySelectorAll('*').forEach(child => {
                            this.translateElement(child);
                        });
                    }
                });
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }
    
    // Initialize
    async init() {
        // Update UI first
        this.updateLanguageSwitcher();
        
        // Translate page if not English
        if (this.currentLang !== 'en') {
            await this.translatePage();
        }
        
        // Watch for dynamic content
        this.observeDOM();
        
        // Setup language switcher clicks
        this.setupLanguageSwitcher();
    }
    
    setupLanguageSwitcher() {
        // Handle dropdown toggle
        document.addEventListener('click', (e) => {
            const languageBtn = document.getElementById('languageBtn');
            const languageMenu = document.getElementById('languageMenu');
            
            if (!languageBtn || !languageMenu) return;
            
            // Toggle dropdown
            if (e.target.closest('#languageBtn')) {
                e.preventDefault();
                e.stopPropagation();
                languageMenu.classList.toggle('hidden');
                return;
            }
            
            // Close dropdown when clicking outside
            if (!e.target.closest('.language-dropdown')) {
                languageMenu.classList.add('hidden');
            }
            
            // Handle language selection
            const langBtn = e.target.closest('[data-lang]');
            if (langBtn && !langBtn.closest('#languageMenu.hidden')) {
                e.preventDefault();
                const lang = langBtn.getAttribute('data-lang');
                
                // Show loading state
                langBtn.style.opacity = '0.5';
                
                this.setLanguage(lang);
            }
        });
        
        // Handle mobile select change
        const mobileSelect = document.getElementById('mobileLangSelect');
        if (mobileSelect) {
            mobileSelect.addEventListener('change', (e) => {
                const lang = e.target.value;
                e.target.style.opacity = '0.5';
                this.setLanguage(lang);
            });
        }
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.professionalTranslate = new ProfessionalTranslate();
        window.professionalTranslate.init();
    });
} else {
    window.professionalTranslate = new ProfessionalTranslate();
    window.professionalTranslate.init();
}
