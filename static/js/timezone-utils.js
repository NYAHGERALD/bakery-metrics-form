/**
 * Timezone Utilities
 * Provides centralized timezone-aware date/time formatting across the application
 * Uses user's saved timezone from database settings
 */

(function() {
    'use strict';

    // Cache for user's timezone setting
    let userTimezone = null;
    let isTimezoneLoaded = false;
    const timezoneLoadPromise = loadUserTimezone();

    /**
     * Load user's timezone setting from database
     * Falls back to localStorage, then system timezone
     */
    async function loadUserTimezone() {
        if (isTimezoneLoaded) {
            return userTimezone;
        }

        try {
            // Try to fetch from database
            const response = await fetch('/api/user-settings');
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.settings && data.settings.timezone) {
                    userTimezone = data.settings.timezone.value;
                    console.log('✅ Loaded timezone from database:', userTimezone);
                    isTimezoneLoaded = true;
                    return userTimezone;
                }
            }
        } catch (error) {
            console.warn('Failed to load timezone from database:', error);
        }

        // Fallback to localStorage
        userTimezone = localStorage.getItem('userTimezone');
        if (userTimezone) {
            console.log('📦 Using timezone from localStorage:', userTimezone);
            isTimezoneLoaded = true;
            return userTimezone;
        }

        // Fallback to system timezone
        try {
            userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            console.log('🌍 Using system timezone:', userTimezone);
        } catch (e) {
            // Ultimate fallback
            userTimezone = 'America/Chicago'; // Default to Central Time
            console.log('⚠️ Using default timezone:', userTimezone);
        }

        isTimezoneLoaded = true;
        return userTimezone;
    }

    /**
     * Get the current user timezone (synchronous)
     * Returns cached value or default if not loaded yet
     */
    function getUserTimezone() {
        return userTimezone || 'America/Chicago';
    }

    /**
     * Format date to locale string with user's timezone
     * @param {Date|string} date - Date object or ISO string
     * @param {Object} options - Intl.DateTimeFormat options
     * @returns {string} Formatted date string
     */
    function formatDate(date, options = {}) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const tz = getUserTimezone();
        
        const defaultOptions = {
            timeZone: tz,
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        };

        const mergedOptions = { ...defaultOptions, ...options };
        
        return dateObj.toLocaleDateString('en-US', mergedOptions);
    }

    /**
     * Format time to locale string with user's timezone
     * @param {Date|string} date - Date object or ISO string
     * @param {Object} options - Intl.DateTimeFormat options
     * @returns {string} Formatted time string
     */
    function formatTime(date, options = {}) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const tz = getUserTimezone();
        
        const defaultOptions = {
            timeZone: tz,
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        };

        const mergedOptions = { ...defaultOptions, ...options };
        
        return dateObj.toLocaleTimeString('en-US', mergedOptions);
    }

    /**
     * Format date and time to locale string with user's timezone
     * @param {Date|string} date - Date object or ISO string
     * @param {Object} options - Intl.DateTimeFormat options
     * @returns {string} Formatted date-time string
     */
    function formatDateTime(date, options = {}) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const tz = getUserTimezone();
        
        const defaultOptions = {
            timeZone: tz,
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        };

        const mergedOptions = { ...defaultOptions, ...options };
        
        return dateObj.toLocaleString('en-US', mergedOptions);
    }

    /**
     * Format date for short display (e.g., "Jan 15")
     * @param {Date|string} date - Date object or ISO string
     * @returns {string} Short formatted date
     */
    function formatDateShort(date) {
        return formatDate(date, {
            month: 'short',
            day: 'numeric'
        });
    }

    /**
     * Format date for long display (e.g., "January 15, 2024")
     * @param {Date|string} date - Date object or ISO string
     * @returns {string} Long formatted date
     */
    function formatDateLong(date) {
        return formatDate(date, {
            month: 'long',
            day: 'numeric',
            year: 'numeric'
        });
    }

    /**
     * Format date range (e.g., "Jan 15 - Jan 20, 2024")
     * @param {Date|string} startDate - Start date
     * @param {Date|string} endDate - End date
     * @returns {string} Formatted date range
     */
    function formatDateRange(startDate, endDate) {
        const start = typeof startDate === 'string' ? new Date(startDate) : startDate;
        const end = typeof endDate === 'string' ? new Date(endDate) : endDate;
        const tz = getUserTimezone();

        const options = { timeZone: tz, month: 'short', day: 'numeric' };
        const startStr = start.toLocaleDateString('en-US', options);

        // If same year, omit year from start date
        if (start.getFullYear() === end.getFullYear()) {
            const endStr = end.toLocaleDateString('en-US', { 
                ...options, 
                year: 'numeric' 
            });
            return `${startStr} - ${endStr}`;
        } else {
            const startStrWithYear = start.toLocaleDateString('en-US', { 
                ...options, 
                year: 'numeric' 
            });
            const endStr = end.toLocaleDateString('en-US', { 
                ...options, 
                year: 'numeric' 
            });
            return `${startStrWithYear} - ${endStr}`;
        }
    }

    /**
     * Get current date/time in user's timezone
     * @returns {Date} Current date in user timezone
     */
    function getNow() {
        const tz = getUserTimezone();
        // Create date with timezone awareness
        const now = new Date();
        
        // Convert to user's timezone by using toLocaleString then parsing back
        const tzDateString = now.toLocaleString('en-US', { timeZone: tz });
        return new Date(tzDateString);
    }

    /**
     * Convert date to user's timezone (for comparisons)
     * @param {Date|string} date - Date to convert
     * @returns {Date} Date object in user's timezone
     */
    function toUserTimezone(date) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const tz = getUserTimezone();
        
        const tzDateString = dateObj.toLocaleString('en-US', { timeZone: tz });
        return new Date(tzDateString);
    }

    /**
     * Get time ago string (e.g., "2 hours ago", "3 days ago")
     * @param {Date|string} date - Date to compare
     * @returns {string} Time ago string
     */
    function getTimeAgo(date) {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const now = new Date();
        const diffMs = now - dateObj;
        const diffSeconds = Math.floor(diffMs / 1000);
        const diffMinutes = Math.floor(diffSeconds / 60);
        const diffHours = Math.floor(diffMinutes / 60);
        const diffDays = Math.floor(diffHours / 24);
        const diffWeeks = Math.floor(diffDays / 7);
        const diffMonths = Math.floor(diffDays / 30);
        const diffYears = Math.floor(diffDays / 365);

        if (diffSeconds < 60) {
            return 'just now';
        } else if (diffMinutes < 60) {
            return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
        } else if (diffHours < 24) {
            return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
        } else if (diffDays < 7) {
            return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
        } else if (diffWeeks < 4) {
            return `${diffWeeks} week${diffWeeks !== 1 ? 's' : ''} ago`;
        } else if (diffMonths < 12) {
            return `${diffMonths} month${diffMonths !== 1 ? 's' : ''} ago`;
        } else {
            return `${diffYears} year${diffYears !== 1 ? 's' : ''} ago`;
        }
    }

    /**
     * Reload timezone setting (call after user updates timezone)
     */
    async function reloadTimezone() {
        isTimezoneLoaded = false;
        userTimezone = null;
        return await loadUserTimezone();
    }

    // Expose utilities globally
    window.TimezoneUtils = {
        loadUserTimezone,
        getUserTimezone,
        formatDate,
        formatTime,
        formatDateTime,
        formatDateShort,
        formatDateLong,
        formatDateRange,
        getNow,
        toUserTimezone,
        getTimeAgo,
        reloadTimezone
    };

    // Auto-load timezone on script load
    console.log('🌐 Timezone utilities loaded');

})();
