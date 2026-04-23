// FACT Service Worker
const CACHE_NAME = 'fact-v57';
const ASSETS = [
  '/fact-prototype/',
  '/fact-prototype/index.html',
  '/fact-prototype/data/topics_meta.json',
  '/fact-prototype/manifest.json',
  'https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;600;700;900&display=swap',
];

// インストール：主要アセットをキャッシュ
self.addEventListener('install', function(e){
  e.waitUntil(
    caches.open(CACHE_NAME).then(function(cache){
      return cache.addAll(ASSETS.filter(function(url){
        return !url.startsWith('https://fonts');
      }));
    })
  );
  self.skipWaiting();
});

// アクティベート：古いキャッシュを削除
self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(
        keys.filter(function(k){ return k !== CACHE_NAME; })
            .map(function(k){ return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

// フェッチ：キャッシュ優先（ネットワーク失敗時はキャッシュから）
self.addEventListener('fetch', function(e){
  // 外部リクエスト（外部リンク遷移等）はスルー
  if(!e.request.url.includes('github.io') && !e.request.url.includes('localhost')){
    return;
  }
  e.respondWith(
    caches.match(e.request).then(function(cached){
      if(cached) return cached;
      return fetch(e.request).then(function(response){
        // index.html と topics_meta.json / topics_detail.json はキャッシュを更新
        if(e.request.url.includes('index.html') || e.request.url.endsWith('/fact-prototype/') || e.request.url.includes('topics_meta.json') || e.request.url.includes('topics_detail.json')){
          var clone = response.clone();
          caches.open(CACHE_NAME).then(function(cache){
            cache.put(e.request, clone);
          });
        }
        return response;
      }).catch(function(){
        // オフライン時はキャッシュのindex.htmlを返す
        return caches.match('/fact-prototype/index.html');
      });
    })
  );
});
