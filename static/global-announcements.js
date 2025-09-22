/**
 * Global Announcement Modal System
 * Displays global announcements as modals after login with 5-second delay
 */

class GlobalAnnouncementModal {
    constructor() {
        this.modalId = 'globalAnnouncementModal';
        this.sessionKey = 'shownGlobalAnnouncements';
        this.loginSessionKey = 'currentLoginSession'; // Track login session
        this.delay = 5000; // 5 seconds
        this.currentAnnouncements = [];
        this.currentIndex = 0;
    }

    /**
     * Initialize the global announcement system
     */
    async init() {
        try {
            // Reset announcement tracking for new login sessions
            await this.resetAnnouncementTrackingIfNewSession();
            
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', () => this.loadAndShowAnnouncements());
            } else {
                this.loadAndShowAnnouncements();
            }
        } catch (error) {
            console.error('Error initializing global announcements:', error);
        }
    }

    /**
     * Reset announcement tracking if this is a new login session
     * This ensures announcements reappear after logout/login cycles
     */
    async resetAnnouncementTrackingIfNewSession() {
        try {
            // Check if we can get user session info from the server
            const response = await fetch('/api/user-status', {
                method: 'GET',
                credentials: 'include'
            });
            
            if (response.ok) {
                const serverData = await response.json();
                
                // Create a unique identifier for this login session
                // Use current timestamp rounded to nearest 10 minutes to allow for short navigation
                const sessionWindow = Math.floor(Date.now() / (10 * 60 * 1000)); // 10-minute windows
                const currentSessionId = `${serverData.user_id || 'unknown'}_${sessionWindow}`;
                const storedSessionId = sessionStorage.getItem(this.loginSessionKey);
                
                if (storedSessionId !== currentSessionId) {
                    console.log('New login session detected - clearing global announcement tracking');
                    console.log('Previous session:', storedSessionId, 'Current session:', currentSessionId);
                    
                    // Clear shown announcements for new session
                    sessionStorage.removeItem(this.sessionKey);
                    
                    // Store new session ID
                    sessionStorage.setItem(this.loginSessionKey, currentSessionId);
                } else {
                    console.log('Same session continuing - preserving announcement tracking');
                }
            } else {
                // If we can't get session info, this might be a fresh login
                console.log('Unable to verify session - clearing announcement tracking to be safe');
                sessionStorage.removeItem(this.sessionKey);
            }
        } catch (error) {
            console.error('Error checking login session:', error);
            // Clear tracking on error to ensure announcements show
            sessionStorage.removeItem(this.sessionKey);
        }
    }

    /**
     * Load global announcements and show them if not seen in this session
     */
    async loadAndShowAnnouncements() {
        try {
            const response = await fetch('/api/global-announcements');
            if (!response.ok) {
                console.log('No global announcements API available or not logged in');
                return;
            }

            const data = await response.json();
            if (!data.success || !data.announcements || data.announcements.length === 0) {
                console.log('No global announcements to display');
                return;
            }

            this.currentAnnouncements = data.announcements;
            this.filterUnseenAnnouncements();

            if (this.currentAnnouncements.length > 0) {
                // Wait 5 seconds before showing announcements
                setTimeout(() => {
                    this.showNextAnnouncement();
                }, this.delay);
            }
        } catch (error) {
            console.error('Error loading global announcements:', error);
        }
    }

    /**
     * Filter out announcements that have been seen in this session
     */
    filterUnseenAnnouncements() {
        const shownAnnouncements = this.getShownAnnouncements();
        this.currentAnnouncements = this.currentAnnouncements.filter(
            announcement => !shownAnnouncements.includes(announcement.id)
        );
    }

    /**
     * Show the next announcement in the queue
     */
    showNextAnnouncement() {
        if (this.currentIndex >= this.currentAnnouncements.length) {
            return; // No more announcements to show
        }

        const announcement = this.currentAnnouncements[this.currentIndex];
        this.createAndShowModal(announcement);
    }

    /**
     * Create and display the announcement modal
     */
    createAndShowModal(announcement) {
        // Remove existing modal if present
        this.removeExistingModal();

        // Create modal HTML
        const modal = this.createModalHTML(announcement);
        document.body.appendChild(modal);

        // Show modal with animation
        requestAnimationFrame(() => {
            modal.classList.remove('hidden');
            modal.classList.add('flex');
        });

        // Add event listeners
        this.attachEventListeners(announcement.id);
    }

    /**
     * Create the modal HTML structure
     */
    createModalHTML(announcement) {
        const modal = document.createElement('div');
        modal.id = this.modalId;
        modal.className = 'hidden fixed inset-0 z-50 items-center justify-center bg-black bg-opacity-50 backdrop-blur-sm';
        
        // Map announcement types to colors and icons
        const typeConfig = {
            'system': { color: 'blue', bgColor: 'from-blue-50 to-indigo-50', border: 'border-blue-500', icon: 'info' },
            'maintenance': { color: 'amber', bgColor: 'from-amber-50 to-orange-50', border: 'border-amber-500', icon: 'wrench' },
            'feature': { color: 'emerald', bgColor: 'from-emerald-50 to-green-50', border: 'border-emerald-500', icon: 'sparkles' },
            'general': { color: 'blue', bgColor: 'from-blue-50 to-indigo-50', border: 'border-blue-500', icon: 'megaphone' }
        };

        const config = typeConfig[announcement.type] || typeConfig['general'];
        const iconName = announcement.icon || config.icon;

        modal.innerHTML = `
            <div class="relative bg-white rounded-2xl max-w-md w-full mx-4 shadow-2xl animate-fade-in-up">
                <!-- Header -->
                <div class="bg-gradient-to-r ${config.bgColor} p-6 rounded-t-2xl border-l-4 ${config.border}">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <div class="w-10 h-10 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
                                <i data-lucide="${iconName}" class="w-5 h-5 text-${config.color}-600"></i>
                            </div>
                            <div>
                                <h3 class="text-lg font-bold text-${config.color}-900">${this.escapeHtml(announcement.title)}</h3>
                                <p class="text-sm text-${config.color}-700 opacity-90">
                                    ${announcement.type.charAt(0).toUpperCase() + announcement.type.slice(1)} Announcement
                                </p>
                            </div>
                        </div>
                        <button id="closeAnnouncementModal" class="text-${config.color}-600 hover:text-${config.color}-800 p-1 rounded-lg hover:bg-white hover:bg-opacity-50 transition-colors">
                            <i data-lucide="x" class="w-5 h-5"></i>
                        </button>
                    </div>
                </div>

                <!-- Content -->
                <div class="p-6">
                    <div class="text-gray-700 leading-relaxed mb-6">
                        ${this.escapeHtml(announcement.content)}
                    </div>
                    
                    <!-- Meta info -->
                    <div class="flex items-center justify-between text-sm text-gray-500 mb-6">
                        <span class="flex items-center space-x-1">
                            <i data-lucide="user" class="w-4 h-4"></i>
                            <span>${this.escapeHtml(announcement.author)}</span>
                        </span>
                        <span class="flex items-center space-x-1">
                            <i data-lucide="calendar" class="w-4 h-4"></i>
                            <span>${announcement.display_date}</span>
                        </span>
                    </div>

                    <!-- Action button -->
                    <div class="flex justify-end">
                        <button id="okAnnouncementModal" class="bg-gradient-to-r from-${config.color}-500 to-${config.color}-600 hover:from-${config.color}-600 hover:to-${config.color}-700 text-white px-6 py-2 rounded-xl font-medium transition-all hover:scale-105 shadow-lg">
                            <i data-lucide="check" class="w-4 h-4 mr-2 inline"></i>
                            OK
                        </button>
                    </div>
                </div>
            </div>
        `;

        return modal;
    }

    /**
     * Attach event listeners to modal buttons
     */
    attachEventListeners(announcementId) {
        const modal = document.getElementById(this.modalId);
        const closeBtn = document.getElementById('closeAnnouncementModal');
        const okBtn = document.getElementById('okAnnouncementModal');

        const handleClose = () => {
            this.closeModal(announcementId);
        };

        closeBtn?.addEventListener('click', handleClose);
        okBtn?.addEventListener('click', handleClose);

        // Close on escape key
        const handleKeydown = (e) => {
            if (e.key === 'Escape') {
                handleClose();
            }
        };

        document.addEventListener('keydown', handleKeydown);

        // Store cleanup function
        modal._cleanup = () => {
            document.removeEventListener('keydown', handleKeydown);
        };
    }

    /**
     * Close the current modal and show next announcement if any
     */
    closeModal(announcementId) {
        // Mark this announcement as seen
        this.markAnnouncementAsSeen(announcementId);

        // Remove modal with animation
        const modal = document.getElementById(this.modalId);
        if (modal) {
            modal.classList.add('opacity-0');
            modal.classList.add('scale-95');
            
            setTimeout(() => {
                if (modal._cleanup) {
                    modal._cleanup();
                }
                modal.remove();
                
                // Show next announcement if any
                this.currentIndex++;
                this.showNextAnnouncement();
            }, 200);
        }
    }

    /**
     * Remove any existing modal
     */
    removeExistingModal() {
        const existingModal = document.getElementById(this.modalId);
        if (existingModal) {
            if (existingModal._cleanup) {
                existingModal._cleanup();
            }
            existingModal.remove();
        }
    }

    /**
     * Mark an announcement as seen in this session
     */
    markAnnouncementAsSeen(announcementId) {
        const shownAnnouncements = this.getShownAnnouncements();
        if (!shownAnnouncements.includes(announcementId)) {
            shownAnnouncements.push(announcementId);
            sessionStorage.setItem(this.sessionKey, JSON.stringify(shownAnnouncements));
        }
    }

    /**
     * Get list of announcements shown in this session
     */
    getShownAnnouncements() {
        try {
            const stored = sessionStorage.getItem(this.sessionKey);
            return stored ? JSON.parse(stored) : [];
        } catch (error) {
            console.error('Error reading shown announcements from session storage:', error);
            return [];
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Auto-initialize when script loads
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize on pages that need global announcements (dashboard, main pages)
    const currentPath = window.location.pathname;
    const validPaths = ['/dashboard', '/form', '/inventory', '/infor', '/', '/user-management'];
    
    if (validPaths.some(path => currentPath.startsWith(path))) {
        const globalAnnouncements = new GlobalAnnouncementModal();
        globalAnnouncements.init();
        
        // Make it globally accessible for debugging
        window.globalAnnouncementModal = globalAnnouncements;
    }
});

// Add CSS animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(30px) scale(0.95);
        }
        to {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    
    .animate-fade-in-up {
        animation: fadeInUp 0.3s ease-out;
    }
    
    #globalAnnouncementModal {
        transition: opacity 0.2s ease-out, backdrop-filter 0.2s ease-out;
    }
    
    #globalAnnouncementModal .opacity-0 {
        opacity: 0;
    }
    
    #globalAnnouncementModal .scale-95 {
        transform: scale(0.95);
    }
`;
document.head.appendChild(style);
