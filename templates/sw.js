{% load static %}
const CACHE_NAME = 'energisuivi-v1';
const ASSETS = [
    '/static/icons/icon-192.svg',
    '/static/icons/icon-512.svg',
    '/static/icons/favicon.svg',
    '/static/icons/logo-bandeau.svg',
    '/static/js/sidebar.js',
];

// URLs à ne JAMAIS intercepter (Django auth + CSRF)
const BYPASS_URLS = [
    '/login',
    '/logout',
    '/register',
    '/admin',
    '/dashboard',
    '/manifest.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // 1. Laisser passer toutes les requêtes POST/PUT/PATCH/DELETE sans interception
    if (event.request.method !== 'GET') return;

    // 2. Laisser passer les URLs Django sensibles
    const isBypass = BYPASS_URLS.some(path => url.pathname.startsWith(path));
    if (isBypass) return;

    // 3. Ne mettre en cache que les fichiers statiques
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                return cached || fetch(event.request).then((response) => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    return response;
                });
            })
        );
        return;
    }

    // 4. Pour tout le reste (pages HTML Django) : toujours aller au réseau
    event.respondWith(fetch(event.request));
});