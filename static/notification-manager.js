// Native Notification Manager
// Handles browser notification permissions and native notifications

class NotificationManager {
  constructor() {
    this.isSupported = 'Notification' in window;
    this.permission = this.isSupported ? Notification.permission : 'denied';
    this.serviceWorkerRegistration = null;
    this.lastNotificationCheck = localStorage.getItem('lastNotificationCheck') || new Date(0).toISOString();
    
    this.init();
  }

  async init() {
    if (!this.isSupported) {
      console.warn('Browser notifications not supported');
      return;
    }

    // Register service worker
    await this.registerServiceWorker();
    
    // Request permission if not already granted
    if (this.permission === 'default') {
      await this.requestPermission();
    }

    // Start checking for new notifications
    this.startNotificationPolling();
  }

  async registerServiceWorker() {
    if ('serviceWorker' in navigator) {
      try {
        this.serviceWorkerRegistration = await navigator.serviceWorker.register('/static/sw.js', {
          scope: '/'
        });
        
        console.log('Service Worker registered successfully:', this.serviceWorkerRegistration);
        
        // Listen for service worker updates
        this.serviceWorkerRegistration.addEventListener('updatefound', () => {
          console.log('Service Worker update found');
        });
        
      } catch (error) {
        console.error('Service Worker registration failed:', error);
      }
    }
  }

  async requestPermission() {
    if (!this.isSupported) return 'denied';
    
    try {
      this.permission = await Notification.requestPermission();
      console.log('Notification permission:', this.permission);
      return this.permission;
    } catch (error) {
      console.error('Error requesting notification permission:', error);
      return 'denied';
    }
  }

  async showNativeNotification(title, options = {}) {
    if (!this.canShowNotifications()) {
      console.warn('Cannot show notifications - permission denied or not supported');
      return null;
    }

    const defaultOptions = {
      icon: '/static/avatar.png',
      badge: '/static/avatar.png',
      tag: 'bakery-notification',
      requireInteraction: false,
      silent: false,
      timestamp: Date.now()
    };

    const notificationOptions = { ...defaultOptions, ...options };

    try {
      // Use service worker to show notification if available
      if (this.serviceWorkerRegistration) {
        return await this.serviceWorkerRegistration.showNotification(title, notificationOptions);
      } else {
        // Fallback to direct browser notification
        const notification = new Notification(title, notificationOptions);
        
        // Auto-close after 5 seconds if not persistent
        if (!notificationOptions.requireInteraction) {
          setTimeout(() => {
            notification.close();
          }, 5000);
        }
        
        return notification;
      }
    } catch (error) {
      console.error('Error showing notification:', error);
      return null;
    }
  }

  canShowNotifications() {
    return this.isSupported && this.permission === 'granted';
  }

  async checkForNewNotifications() {
    try {
      const response = await fetch('/api/notifications', {
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.success && data.notifications) {
        // Filter notifications newer than last check
        const lastCheck = new Date(this.lastNotificationCheck);
        const newNotifications = data.notifications.filter(notification => 
          new Date(notification.created_at) > lastCheck
        );

        // Show native notifications for new items
        for (const notification of newNotifications) {
          await this.showNotificationFromData(notification);
        }

        // Update last check time
        this.lastNotificationCheck = new Date().toISOString();
        localStorage.setItem('lastNotificationCheck', this.lastNotificationCheck);

        return newNotifications;
      }
    } catch (error) {
      console.error('Error checking for notifications:', error);
      return [];
    }
  }

  async showNotificationFromData(notificationData) {
    const iconMap = {
      'form_submission': '/static/avatar.png',
      'issue_report': '/static/avatar.png',
      'inventory_alert': '/static/avatar.png',
      'kpi_alert': '/static/avatar.png',
      'week_update': '/static/avatar.png'
    };

    const titleMap = {
      'form_submission': 'Form Submission',
      'issue_report': 'Issue Report',
      'inventory_alert': 'Inventory Update',
      'kpi_alert': 'Performance Alert',
      'week_update': 'Week Update'
    };

    const urgencyMap = {
      'kpi_alert': true,
      'issue_report': true,
      'inventory_alert': false,
      'form_submission': false,
      'week_update': false
    };

    const title = titleMap[notificationData.type] || 'Bakery Notification';
    const options = {
      body: notificationData.description,
      icon: iconMap[notificationData.type] || '/static/avatar.png',
      badge: '/static/avatar.png',
      tag: `bakery-${notificationData.type}-${Date.now()}`,
      timestamp: new Date(notificationData.created_at).getTime(),
      requireInteraction: urgencyMap[notificationData.type] || false,
      data: {
        type: notificationData.type,
        url: '/',
        timestamp: notificationData.created_at
      }
    };

    // Add vibration for mobile devices on urgent notifications
    if (urgencyMap[notificationData.type] && 'vibrate' in navigator) {
      options.vibrate = [200, 100, 200];
    }

    return await this.showNativeNotification(title, options);
  }

  startNotificationPolling() {
    // Check for new notifications every 30 seconds
    setInterval(async () => {
      if (document.visibilityState === 'hidden' || !document.hasFocus()) {
        // Only check when app is in background
        await this.checkForNewNotifications();
      }
    }, 30000);

    // Also check when page becomes visible again
    document.addEventListener('visibilitychange', async () => {
      if (document.visibilityState === 'visible') {
        await this.checkForNewNotifications();
      }
    });
  }

  // Enhanced notification with custom sounds
  async showEnhancedNotification(title, options = {}) {
    const notification = await this.showNativeNotification(title, options);
    
    // Play custom sound if enabled and supported
    if (notification && this.shouldPlaySound()) {
      this.playNotificationSound(options.type);
    }
    
    return notification;
  }

  shouldPlaySound() {
    // Check user preferences for sound alerts
    const soundEnabled = localStorage.getItem('soundAlerts') !== 'false';
    return soundEnabled && 'Audio' in window;
  }

  playNotificationSound(type = 'default') {
    try {
      // You can add different sounds for different notification types
      const soundMap = {
        'kpi_alert': 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBzWN1+/QfCkFJnbO8tyQQAoUXbPt46hVFApFnt/xwW4hBjWJ2O/TgCkFJnbQ8t6RQAoUXbPr56tWFAlGoN7uuWMdBziS1+3SfCgGJnfI9N2QQAoUXrLr46tVFAlFnt/yv2sjBzWI2e/UfioEK3bQ8t6RQAoUXrPq6alVFAlGnt/yvmojBjWK1+7SfCkEKHbI9N2QQgoTXbLr46tVFAlFnt/ywW0jBjWI2e7TgCkEJnfO8t6SQAkUXrPr5qpWFApGoN7wuWEfBziR2O3SfisEJnbI9N2QQAoUXbTq56tWFAlGnt/ywG4jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24j',
        'issue_report': 'data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBzWN1+/QfCkFJnbO8tyQQAoUXbPt46hVFApFnt/xwW4hBjWJ2O/TgCkFJnbQ8t6RQAoUXbPr56tWFAlGoN7uuWMdBziS1+3SfCgGJnfI9N2QQAoUXrLr46tVFAlFnt/yv2sjBzWI2e/UfioEK3bQ8t6RQAoUXrPq6alVFAlGnt/yvmojBjWK1+7SfCkEKHbI9N2QQgoTXbLr46tVFAlFnt/ywW0jBjWI2e7TgCkEJnfO8t6SQAkUXrPr5qpWFApGoN7wuWEfBziR2O3SfisEJnbI9N2QQAoUXbTq56tWFAlGnt/ywG4jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24jBjWI2e/SgCoEJnbO8t6SQAkTXbPr5qpWFApGoN7xw24j'
      };
      
      const audio = new Audio(soundMap[type] || soundMap['default']);
      audio.volume = 0.3;
      audio.play().catch(error => {
        console.log('Could not play notification sound:', error);
      });
    } catch (error) {
      console.log('Error playing notification sound:', error);
    }
  }

  // Method to get notification statistics
  getNotificationStats() {
    return {
      isSupported: this.isSupported,
      permission: this.permission,
      canShow: this.canShowNotifications(),
      serviceWorkerActive: !!this.serviceWorkerRegistration,
      lastCheck: this.lastNotificationCheck
    };
  }
}

// Create global instance
window.notificationManager = new NotificationManager();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = NotificationManager;
}
