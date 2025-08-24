// Service Worker for Native Push Notifications
// Handles background push notifications and caching

const CACHE_NAME = 'bakery-metrics-v1';
const urlsToCache = [
  '/',
  '/static/css/output.css',
  '/static/avatar.png',
  '/static/default-avatar.png'
];

// Install event - cache resources
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching resources');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Service Worker: Clearing old cache', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache when offline
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version or fetch from network
        return response || fetch(event.request);
      }
    )
  );
});

// Push event - handle incoming push notifications
self.addEventListener('push', event => {
  console.log('Service Worker: Push event received', event);
  
  let notificationData = {
    title: 'Bakery Metrics',
    body: 'New notification available',
    icon: '/static/avatar.png',
    badge: '/static/avatar.png',
    tag: 'bakery-notification',
    data: {
      url: '/'
    }
  };

  // Parse push data if available
  if (event.data) {
    try {
      const pushData = event.data.json();
      notificationData = {
        ...notificationData,
        ...pushData
      };
    } catch (e) {
      console.log('Service Worker: Error parsing push data', e);
      notificationData.body = event.data.text() || notificationData.body;
    }
  }

  const notificationOptions = {
    body: notificationData.body,
    icon: notificationData.icon,
    badge: notificationData.badge,
    tag: notificationData.tag,
    data: notificationData.data,
    requireInteraction: false,
    actions: [
      {
        action: 'view',
        title: 'View Details',
        icon: '/static/avatar.png'
      },
      {
        action: 'dismiss',
        title: 'Dismiss',
        icon: '/static/avatar.png'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(notificationData.title, notificationOptions)
  );
});

// Notification click event
self.addEventListener('notificationclick', event => {
  console.log('Service Worker: Notification clicked', event);
  
  event.notification.close();

  if (event.action === 'dismiss') {
    return;
  }

  // Default action or 'view' action
  const urlToOpen = event.notification.data?.url || '/';
  
  event.waitUntil(
    clients.matchAll({
      type: 'window',
      includeUncontrolled: true
    }).then(clientList => {
      // Check if app is already open
      for (const client of clientList) {
        if (client.url.includes(new URL(urlToOpen, self.location.origin).pathname)) {
          return client.focus();
        }
      }
      
      // Open new window if app is not open
      return clients.openWindow(urlToOpen);
    })
  );
});

// Background sync for offline notifications
self.addEventListener('sync', event => {
  if (event.tag === 'background-sync-notifications') {
    event.waitUntil(syncNotifications());
  }
});

async function syncNotifications() {
  try {
    const response = await fetch('/api/notifications');
    const data = await response.json();
    
    if (data.success && data.notifications?.length > 0) {
      // Check for new notifications compared to last sync
      const lastSyncTime = await getLastSyncTime();
      const newNotifications = data.notifications.filter(notification => 
        new Date(notification.created_at) > new Date(lastSyncTime)
      );
      
      // Show native notifications for new items
      for (const notification of newNotifications) {
        await showNativeNotification(notification);
      }
      
      // Update last sync time
      await setLastSyncTime(new Date().toISOString());
    }
  } catch (error) {
    console.error('Service Worker: Error syncing notifications:', error);
  }
}

async function getLastSyncTime() {
  const cache = await caches.open(CACHE_NAME);
  const response = await cache.match('/last-sync-time');
  return response ? await response.text() : new Date(0).toISOString();
}

async function setLastSyncTime(time) {
  const cache = await caches.open(CACHE_NAME);
  await cache.put('/last-sync-time', new Response(time));
}

async function showNativeNotification(notification) {
  const iconMap = {
    'form_submission': '/static/avatar.png',
    'issue_report': '/static/avatar.png',
    'inventory_alert': '/static/avatar.png',
    'kpi_alert': '/static/avatar.png',
    'week_update': '/static/avatar.png'
  };

  const notificationOptions = {
    body: notification.description,
    icon: iconMap[notification.type] || '/static/avatar.png',
    badge: '/static/avatar.png',
    tag: `bakery-${notification.type}-${Date.now()}`,
    timestamp: new Date(notification.created_at).getTime(),
    requireInteraction: false,
    data: {
      type: notification.type,
      url: '/',
      notificationId: notification.id
    }
  };

  await self.registration.showNotification(
    getNotificationTitle(notification.type),
    notificationOptions
  );
}

function getNotificationTitle(type) {
  const titleMap = {
    'form_submission': 'Form Submission',
    'issue_report': 'Issue Report',
    'inventory_alert': 'Inventory Update',
    'kpi_alert': 'Performance Alert',
    'week_update': 'Week Update'
  };
  return titleMap[type] || 'Bakery Notification';
}
