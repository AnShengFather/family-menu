self.addEventListener("install", function(e){self.skipWaiting()});
self.addEventListener("activate", function(e){e.waitUntil(clients.claim())});
self.addEventListener("fetch", function(e){
  e.respondWith(
    fetch(e.request).catch(function(){return new Response("离线无法访问",{status:503})})
  );
});
