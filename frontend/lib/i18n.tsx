"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

export type Locale = "tr" | "en";
const STORAGE_KEY = "odin_locale";
const DEFAULT_LOCALE: Locale = "tr";

// Flat, dotted-key dictionary. t(key) → current-locale string (falls back to the key).
const M: Record<string, { tr: string; en: string }> = {
  // nav / header
  "nav.console": { tr: "Konsol", en: "Console" },
  "nav.postNow": { tr: "Şimdi paylaş", en: "Post now" },
  "nav.topics": { tr: "Konular", en: "Topics" },
  "nav.tester": { tr: "Test", en: "Tester" },
  "nav.profile": { tr: "Profil", en: "Profile" },
  "nav.drafts": { tr: "Taslaklar", en: "Drafts" },
  "nav.learning": { tr: "Öğrenme", en: "Learning" },
  "nav.sources": { tr: "Kaynaklar", en: "Sources" },
  "nav.system": { tr: "Sistem", en: "System" },
  "nav.compose": { tr: "Tweet üret", en: "Compose" },

  // composer
  "co.title": { tr: "Tweet üret", en: "Compose a post" },
  "co.subtitle": {
    tr: "İstediğin konuyu yaz, istediğin formatta tweet üretsin.",
    en: "Type any topic and generate posts in the format you want.",
  },
  "co.topic": { tr: "Konu", en: "Topic" },
  "co.topicPlaceholder": {
    tr: "Ne hakkında yazmak istiyorsun?",
    en: "What do you want to post about?",
  },
  "co.audience": { tr: "Kitle", en: "Audience" },
  "co.aud.technical": { tr: "Teknik", en: "Technical" },
  "co.aud.general": { tr: "Genel (teknik değil)", en: "General (non-technical)" },
  "co.format": { tr: "Format", en: "Format" },
  "co.fmt.short": { tr: "Kısa (≤280)", en: "Short (≤280)" },
  "co.fmt.long": { tr: "Uzun", en: "Long" },
  "co.fmt.story": { tr: "Hikaye", en: "Story" },
  "co.fmt.thread": { tr: "Thread (4-6)", en: "Thread (4-6)" },
  "co.style": { tr: "Tarz", en: "Style" },
  "co.style.mine": { tr: "Kendi tarzım", en: "My own voice" },
  "co.generate": { tr: "Üret", en: "Generate" },
  "co.generating": { tr: "Üretiliyor…", en: "Generating…" },
  "co.empty": {
    tr: "Bir konu yaz ve Üret'e bas.",
    en: "Type a topic and hit Generate.",
  },
  "nav.grp.discover": { tr: "Keşif", en: "Discover" },
  "nav.grp.you": { tr: "Sen", en: "You" },
  "nav.grp.system": { tr: "Sistem", en: "System" },
  "nav.notifications": { tr: "Bildirimler", en: "Notifications" },
  "nav.menu": { tr: "Menü", en: "Menu" },
  "nav.tagline": { tr: "İstihbarat konsolu", en: "Intelligence console" },

  // system / observability
  "sys.title": { tr: "Sistem", en: "System" },
  "sys.subtitle": {
    tr: "AI maliyeti ve işlem günlükleri",
    en: "AI cost and pipeline logs",
  },
  "sys.costTotal": { tr: "Toplam maliyet", en: "Total cost" },
  "sys.cost30d": { tr: "Son 30 gün", en: "Last 30 days" },
  "sys.calls": { tr: "LLM çağrısı", en: "LLM calls" },
  "sys.tokens": { tr: "Toplam token", en: "Total tokens" },
  "sys.byPurpose": { tr: "Amaca göre maliyet", en: "Cost by purpose" },
  "sys.purpose": { tr: "Amaç", en: "Purpose" },
  "sys.tokensCol": { tr: "Token", en: "Tokens" },
  "sys.costCol": { tr: "Maliyet", en: "Cost" },
  "sys.runs": { tr: "Son işlemler", en: "Recent runs" },
  "sys.runKind": { tr: "Tür", en: "Kind" },
  "sys.runItems": { tr: "Öğe", en: "Items" },
  "sys.runEvents": { tr: "Olay", en: "Events" },
  "sys.runErrors": { tr: "Hata", en: "Errors" },
  "sys.runTime": { tr: "Zaman", en: "Time" },
  "sys.noRuns": { tr: "Henüz işlem yok", en: "No runs yet" },

  // sources
  "src.title": { tr: "Kaynaklar", en: "Sources" },
  "src.subtitle": {
    tr: "ODIN'in izlediği içerik kaynakları. RSS ekle, aç/kapat, sağlığı gör.",
    en: "The content sources ODIN watches. Add RSS, enable/disable, see health.",
  },
  "src.add": { tr: "Kaynak ekle", en: "Add source" },
  "src.adding": { tr: "Ekleniyor…", en: "Adding…" },
  "src.name": { tr: "Ad", en: "Name" },
  "src.url": { tr: "RSS URL", en: "RSS URL" },
  "src.healthy": { tr: "sağlıklı", en: "healthy" },
  "src.failing": { tr: "hata", en: "failing" },
  "src.never": { tr: "hiç çekilmedi", en: "never polled" },
  "src.remove": { tr: "kaldır", en: "remove" },
  "src.empty": { tr: "Henüz kaynak yok. İlk RSS'i yukarıdan ekle.", en: "No sources yet. Add your first RSS above." },

  // performance (profile)
  "pf.performance": { tr: "Senin için ne işe yarıyor", en: "What works for you" },
  "pf.byType": { tr: "İçerik tipine göre", en: "By content type" },
  "pf.byTopic": { tr: "Konuya göre", en: "By topic" },
  "pf.noPerf": {
    tr: "Henüz performans verisi yok. Gönderilerini içe aktar.",
    en: "No performance data yet. Import your posts.",
  },
  "pf.postsN": { tr: "gönderi", en: "posts" },
  "pf.growth": { tr: "Takipçi büyümesi", en: "Follower growth" },
  "pf.growthHint": {
    tr: "Kendi profilinde gezindikçe uzantı sayıları kaydeder.",
    en: "The extension records your counts as you browse your own profile.",
  },
  "pf.followers": { tr: "Takipçi", en: "Followers" },
  "pf.following": { tr: "Takip", en: "Following" },
  "pf.tweets": { tr: "Gönderi", en: "Posts" },
  "pf.snapshotsN": { tr: "anlık kayıt", en: "snapshots" },
  "pf.noGrowth": {
    tr: "Henüz profil verisi yok — uzantıda handle'ını ayarla ve X profilini aç.",
    en: "No profile data yet — set your handle in the extension and visit your X profile.",
  },
  "pf.myTweets": { tr: "Attığın tweetler", en: "Your tweets" },
  "pf.myTweetsHint": {
    tr: "Uzantının içe aktardığı kendi gönderilerin ve etkileşimleri",
    en: "Your own posts the extension imported, with engagement",
  },
  "pf.noTweets": {
    tr: "Henüz tweet yok — uzantıda handle'ını ayarla ve kendi profilinde gezin.",
    en: "No tweets yet — set your handle in the extension and browse your own profile.",
  },
  "pf.mLikes": { tr: "beğeni", en: "likes" },
  "pf.mReposts": { tr: "RT", en: "reposts" },
  "pf.mReplies": { tr: "yanıt", en: "replies" },
  "pf.mViews": { tr: "görüntülenme", en: "views" },

  // best time to post
  "tm.title": { tr: "En iyi paylaşım zamanı", en: "Best time to post" },
  "tm.hint": {
    tr: "Kendi gönderilerinin etkileşimine göre — kitlen ne zaman aktif",
    en: "From your own posts' engagement — when your audience is active",
  },
  "tm.bestHour": { tr: "En iyi saat", en: "Best hour" },
  "tm.bestDay": { tr: "En iyi gün", en: "Best day" },
  "tm.byHour": { tr: "Saate göre", en: "By hour" },
  "tm.byDay": { tr: "Güne göre", en: "By day" },
  "tm.notEnough": {
    tr: "Yeterli veri yok — en az {n} gönderi gerekiyor. Uzantı kendi tweetlerini topladıkça dolacak.",
    en: "Not enough data yet — needs at least {n} posts. It fills up as the extension imports your tweets.",
  },
  "header.signOut": { tr: "Çıkış", en: "Sign out" },
  "header.notifications": { tr: "Bildirimler", en: "Notifications" },

  // common states
  "state.scanning": { tr: "Sinyaller taranıyor…", en: "Scanning signals…" },
  "state.loading": { tr: "Yükleniyor…", en: "Loading…" },
  "state.signalLost": { tr: "Sinyal kayboldu", en: "Signal lost" },
  "state.apiHint": { tr: "API çalışıyor mu:", en: "Is the API running at" },
  "state.retry": { tr: "Tekrar dene", en: "Retry" },

  // login
  "login.title": { tr: "Giriş yap", en: "Sign in" },
  "login.subtitle": { tr: "Erişim kısıtlı.", en: "Access is restricted." },
  "login.username": { tr: "Kullanıcı adı", en: "Username" },
  "login.password": { tr: "Şifre", en: "Password" },
  "login.submit": { tr: "Giriş yap", en: "Sign in" },
  "login.submitting": { tr: "Giriş yapılıyor…", en: "Signing in…" },
  "login.invalid": { tr: "Geçersiz kimlik bilgileri", en: "Invalid credentials" },

  // dashboard
  "dash.title": { tr: "En iyi fırsatlar", en: "Top opportunities" },
  "dash.subtitle": {
    tr: "Trend momentumuna göre sıralanan gelişen olaylar. Ingestion worker'ı sürekli günceller.",
    en: "Emerging events ranked by trend momentum. Updated continuously by the ingestion worker.",
  },
  "dash.tracked": { tr: "olay izleniyor", en: "events tracked" },
  "dash.empty": {
    tr: "Henüz olay yok. Kaynakları ekleyip ingestion worker'ı çalıştır.",
    en: "No events yet. Seed sources and run the ingestion worker to populate the console.",
  },
  "onboard.title": { tr: "Fırsatlar nereden geliyor?", en: "Where do opportunities come from?" },
  "onboard.body": {
    tr: "ODIN; RSS, Hacker News, GitHub, Reddit ve X'ten olayları toplar, kümeler ve puanlar. Sana özel fırsatlar için konularını ekle — böylece hangi olayların senin için önemli olduğunu bilir. Konu olmadan sadece genel trendleri görürsün.",
    en: "ODIN gathers events from RSS, Hacker News, GitHub, Reddit and X, clusters and scores them. Add your topics so ODIN knows which events matter to you — without topics you only see general trends.",
  },
  "onboard.cta": { tr: "Konularını ekle →", en: "Add your topics →" },
  "ev.forYou": { tr: "sana uygun", en: "for you" },
  "greet.morning": { tr: "Günaydın", en: "Good morning" },
  "greet.afternoon": { tr: "İyi günler", en: "Good afternoon" },
  "greet.evening": { tr: "İyi akşamlar", en: "Good evening" },
  "dash.foundN": { tr: "{n} olay izliyorum", en: "I'm tracking {n} events" },
  "dash.relevantM": { tr: "{m} tanesi sana yüksek fırsat", en: "{m} are high-opportunity for you" },
  "dash.allQuiet": { tr: "şu an öne çıkan fırsat yok", en: "nothing stands out right now" },
  "dash.search": { tr: "Olay veya başlık ara…", en: "Search events or headlines…" },
  "dash.searchNone": {
    tr: "\"{q}\" için sonuç yok. Farklı bir kelime dene.",
    en: "Nothing found for \"{q}\". Try a different word.",
  },
  "dash.searchResults": { tr: "Arama sonuçları", en: "Search results" },
  "dash.searchHint": { tr: "başlıklarda da arar", en: "also searches merged headlines" },
  "ev.alsoCovers": { tr: "Bu olaydaki diğer başlıklar", en: "Also in this event" },
  "dash.statTracked": { tr: "İzlenen olay", en: "Tracked" },
  "dash.statActNow": { tr: "Şimdi değerlendir", en: "Act now" },
  "dash.statForYou": { tr: "Sana uygun", en: "For you" },
  "dash.statTopOpp": { tr: "En yüksek fırsat", en: "Top opportunity" },
  "dash.actNow": { tr: "Şimdi değerlendir", en: "Act now" },
  "dash.actNowHint": {
    tr: "Fırsat skoru yüksek — hızlı davranmaya değer",
    en: "High opportunity score — worth moving on quickly",
  },
  "dash.watching": { tr: "İzlemede", en: "Watching" },
  "dash.watchingHint": {
    tr: "Momentum kazanıyor, henüz aksiyon zamanı değil",
    en: "Gaining momentum, not yet time to act",
  },

  // event card / detail
  "ev.source": { tr: "kaynak", en: "source" },
  "ev.sources": { tr: "kaynak", en: "sources" },
  "ev.item": { tr: "içerik", en: "item" },
  "ev.items": { tr: "içerik", en: "items" },
  "ev.back": { tr: "← konsola dön", en: "← back to console" },
  "ev.trend": { tr: "Trend", en: "Trend" },
  "ev.dismiss": { tr: "İlgilenmiyorum", en: "Not interested" },
  "ev.gone": {
    tr: "Bu olay artık mevcut değil (silinmiş ya da temizlenmiş olabilir).",
    en: "This event no longer exists (it may have been dismissed or cleared).",
  },
  "ev.opportunity": { tr: "Fırsat", en: "Opportunity" },
  "ev.personal": { tr: "Kişisel", en: "Personal" },
  "ev.confidence": { tr: "Güven", en: "Confidence" },
  "ev.signalBreakdown": { tr: "Sinyal dökümü", en: "Signal breakdown" },
  "ev.noSignal": { tr: "Sinyal verisi yok.", en: "No signal data." },
  "ev.sourcesN": { tr: "Kaynaklar", en: "Sources" },
  "ev.sharing": { tr: "Paylaşılanlar", en: "What people are sharing" },

  // post-now
  "pn.title": { tr: "Şimdi ne paylaşmalıyım?", en: "What should I post now?" },
  "pn.subtitle": {
    tr: "Fırsata göre sıralı — trend momentumu; kişisel ilgi, zamanlama ve kaynak güveniyle ağırlıklandırılmış.",
    en: "Events ranked by opportunity — trend momentum weighted by your personal relevance, timing and source confidence.",
  },
  "pn.empty": {
    tr: "Henüz fırsat yok. Konu ekle ve ingestion çalıştır.",
    en: "No opportunities yet. Add topics and run ingestion.",
  },
  "pn.opp": { tr: "Fırsat", en: "Opp." },
  "pn.you": { tr: "Sen", en: "You" },
  "action.postNow": { tr: "ŞİMDİ PAYLAŞ", en: "POST NOW" },
  "action.within30": { tr: "30 DK İÇİNDE", en: "POST WITHIN 30 MIN" },
  "action.consider": { tr: "DEĞERLENDİR", en: "CONSIDER" },
  "action.wait": { tr: "BEKLE", en: "WAIT" },

  // topics
  "tp.title": { tr: "Konular", en: "Topics" },
  "tp.subtitle": {
    tr: "ODIN'in senin için neyi izleyeceğini tanımla. Anahtar kelimeler ilgiyi artırır; hariç tutulanlar bastırır.",
    en: "Define what ODIN should watch for you. Keywords boost relevance; excluded terms suppress matches.",
  },
  "tp.name": { tr: "Ad", en: "Name" },
  "tp.keywords": { tr: "Anahtar kelimeler (virgülle)", en: "Keywords (comma-sep)" },
  "tp.exclude": { tr: "Hariç tut", en: "Exclude" },
  "tp.add": { tr: "Konu ekle", en: "Add topic" },
  "tp.adding": { tr: "Ekleniyor…", en: "Adding…" },
  "tp.remove": { tr: "kaldır", en: "remove" },
  "tp.empty": { tr: "Henüz konu yok. İlkini yukarıdan ekle.", en: "No topics yet. Add your first above." },
  "tp.not": { tr: "hariç:", en: "not:" },

  // tester
  "ts.title": { tr: "Tweet test", en: "Tweet tester" },
  "ts.subtitle": {
    tr: "Bir taslak yapıştır. ODIN X Algoritma Simülasyonu, stil uyumun, güncel trend uyumu ve özgünlükle potansiyeli tahmin eder.",
    en: "Paste a draft. ODIN estimates its potential using an X Algorithm Simulation, your style fit, current trend fit and novelty.",
  },
  "ts.placeholder": { tr: "Gönderini yapıştır…", en: "Paste your post…" },
  "ts.analyze": { tr: "Analiz et", en: "Analyze" },
  "ts.analyzing": { tr: "Analiz ediliyor…", en: "Analyzing…" },
  "ts.viral": { tr: "Viral potansiyel", en: "Viral potential" },
  "ts.xsim": { tr: "X simülasyonu", en: "X simulation" },
  "ts.personalFit": { tr: "Kişisel uyum", en: "Personal fit" },
  "ts.trendFit": { tr: "Trend uyumu", en: "Trend fit" },
  "ts.breakdown": { tr: "Döküm", en: "Breakdown" },
  "ts.novelty": { tr: "Özgünlük", en: "Novelty" },
  "ts.reply": { tr: "Yanıt potansiyeli", en: "Reply potential" },
  "ts.bookmark": { tr: "Kaydetme potansiyeli", en: "Bookmark potential" },
  "ts.negative": { tr: "Negatif risk", en: "Negative risk" },
  "ts.why": { tr: "Neden işe yarar", en: "Why it works" },
  "ts.watch": { tr: "Dikkat edilecekler", en: "What to watch" },

  // profile
  "pf.title": { tr: "Stil profilin", en: "Your style profile" },
  "pf.subtitle": {
    tr: "İçe aktarılan gönderilerinden öğrenilen, nasıl yazdığının parmak izi (X toplayıcı ile).",
    en: "A fingerprint of how you write, learned from your imported posts (via the X collector).",
  },
  "pf.rebuild": { tr: "Yeniden oluştur", en: "Rebuild" },
  "pf.rebuilding": { tr: "Oluşturuluyor…", en: "Rebuilding…" },
  "pf.empty": {
    tr: "Henüz stil profili yok. X toplayıcı ile gönderi içe aktar, sonra Yeniden oluştur.",
    en: "No style profile yet. Import posts with the X collector, then Rebuild.",
  },
  "pf.analyzed": { tr: "gönderi analiz edildi", en: "posts analyzed" },
  "pf.terms": { tr: "Sık kullanılan terimler", en: "Frequent terms" },

  // drafts
  "df.title": { tr: "Taslaklar & kuyruk", en: "Drafts & queue" },
  "df.subtitle": {
    tr: "Onaylanan içerik, tahmini kaydedilmiş. X'te kendin paylaş, sonra gönderi id'sini yapıştır ki ODIN tahmin-gerçek karşılaştırsın.",
    en: "Approved content, with its prediction stored. Post it on X yourself, then paste the post id so ODIN can compare prediction vs. reality.",
  },
  "df.empty": {
    tr: "Henüz taslak yok. Bir olaydan aday onaylayarak kuyruğa ekle.",
    en: "No drafts yet. Approve a candidate from an event to queue it here.",
  },
  "df.pasteId": { tr: "Paylaştıktan sonra X gönderi id'sini yapıştır", en: "Paste the X post id after posting" },
  "df.markPosted": { tr: "Paylaşıldı işaretle", en: "Mark posted" },
  "df.posted": { tr: "paylaşıldı · id", en: "posted · id" },

  // learning
  "ln.title": { tr: "Öğrenme", en: "Learning" },
  "ln.subtitle": {
    tr: "Tahmin vs gerçek. Onaylı taslakları paylaşıp metrikleri (X toplayıcı ile) geldikçe ODIN tahmininin ne kadar isabetli olduğunu ölçer.",
    en: "Prediction vs. actual. Once you post approved drafts and their metrics come back (via the X collector), ODIN measures how accurate its predictions were.",
  },
  "ln.empty": {
    tr: "Değerlendirilecek bir şey yok. Onaylı bir taslak paylaş, sonra metriklerini içe aktar.",
    en: "Nothing to evaluate yet. Post an approved draft, then import its metrics.",
  },
  "ln.evaluated": { tr: "Değerlendirilen", en: "Evaluated" },
  "ln.perPost": { tr: "Gönderi başına", en: "Per post" },
  "ln.calibration": { tr: "Kalibrasyon", en: "Calibration" },
  "ln.calibrationHint": {
    tr: "Geçmiş tahmin hataların bir sonraki tahmine otomatik uygulanır — model kendini düzeltir.",
    en: "Past prediction error is folded into the next prediction — the model self-corrects.",
  },
  "ln.bias.under": { tr: "Düşük tahmin ediyorduk, yukarı düzeltildi", en: "We under-predicted; corrected up" },
  "ln.bias.over": { tr: "Yüksek tahmin ediyorduk, aşağı düzeltildi", en: "We over-predicted; corrected down" },
  "ln.bias.none": { tr: "Tahminler isabetli", en: "Predictions are on target" },
  "ln.impPerLike": { tr: "beğeni başına ~{n} görüntülenme", en: "~{n} views per like" },
  "ln.pred": { tr: "tahmin", en: "pred" },
  "ln.act": { tr: "gerçek", en: "act" },

  // notifications
  "nt.title": { tr: "Bildirimler", en: "Notifications" },
  "nt.subtitle": {
    tr: "Ingestion pipeline'dan yüksek fırsatlı olaylar ve operasyonel uyarılar.",
    en: "High-opportunity events and operational alerts from the ingestion pipeline.",
  },
  "nt.empty": { tr: "Henüz bildirim yok.", en: "No notifications yet." },
  "nt.markRead": { tr: "okundu işaretle", en: "mark read" },

  // content panel
  "cp.generate": { tr: "İçerik üret", en: "Generate content" },
  "cp.generateAngles": { tr: "Açı üret", en: "Generate angles" },
  "cp.lang": { tr: "Dil", en: "Language" },
  "cp.kind": { tr: "Tweet türü", en: "Tweet kind" },
  "cp.kind.all": { tr: "Tüm açılar", en: "All angles" },
  "cp.kind.breaking": { tr: "Son dakika", en: "Breaking" },
  "cp.kind.contrarian": { tr: "Karşıt görüş", en: "Contrarian" },
  "cp.kind.technical": { tr: "Teknik detay", en: "Technical" },
  "cp.kind.educational": { tr: "Öğretici", en: "Educational" },
  "cp.kind.question": { tr: "Soru / tartışma", en: "Question" },
  "cp.length": { tr: "Uzunluk", en: "Length" },
  "cp.length.short": { tr: "Kısa (≤280)", en: "Short (≤280)" },
  "cp.length.long": { tr: "Uzun", en: "Long" },
  "cp.copy": { tr: "Kopyala", en: "Copy" },
  "cp.copySource": { tr: "Kaynakla kopyala", en: "Copy + source" },
  "cp.copied": { tr: "Kopyalandı ✓", en: "Copied ✓" },
  "cp.edit": { tr: "Düzenle", en: "Edit" },
  "cp.save": { tr: "Kaydet", en: "Save" },
  "cp.cancel": { tr: "Vazgeç", en: "Cancel" },
  "cp.delete": { tr: "Sil", en: "Delete" },
  "cp.chars": { tr: "{n} karakter", en: "{n} chars" },
  "cp.ai": { tr: "Yapay zekaya söyle", en: "Tell the AI" },
  "cp.aiPlaceholder": {
    tr: "örn. bu makaleyi okumuşum gibi özetle, daha samimi yaz, kısalt…",
    en: "e.g. summarise it as if I read the article, make it warmer, shorten it…",
  },
  "cp.aiRun": { tr: "Uygula", en: "Apply" },
  "cp.aiRunning": { tr: "Yazılıyor…", en: "Rewriting…" },
  "cp.aiHint": {
    tr: "Metni yapay zekaya istediğin gibi yeniden yazdır, sonra Kaydet'e bas.",
    en: "Have the AI rewrite the text however you want, then hit Save.",
  },
  "cp.image": { tr: "Önerilen görsel", en: "Suggested image" },
  "cp.imageHint": {
    tr: "Kaynaktan alındı — tweete eklemek için indir veya bağlantıyı kopyala",
    en: "Pulled from the source — download it or copy the link to attach",
  },
  "cp.copyImage": { tr: "Görsel bağlantısı", en: "Copy image link" },
  "cp.openImage": { tr: "Aç", en: "Open" },
  "cp.regenerate": { tr: "Yeniden üret", en: "Regenerate" },
  "cp.generating": { tr: "Üretiliyor…", en: "Generating…" },
  "cp.none": {
    tr: "Henüz aday yok. Bu olay için farklı stratejik açılar üret.",
    en: "No candidates yet. Generate distinct strategic angles for this event.",
  },
  "cp.approve": { tr: "Onayla →", en: "Approve →" },
  "cp.approving": { tr: "Onaylanıyor…", en: "Approving…" },
  "cp.approvedLikes": { tr: "onaylandı · ~{n} beğeni tahmini", en: "approved · ~{n} likes predicted" },
};

interface I18n {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    // Hydrate the persisted preference after mount (avoids SSR/client mismatch).
    const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (saved === "tr" || saved === "en") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLocaleState(saved);
    }
  }, []);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    localStorage.setItem(STORAGE_KEY, l);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      let s = M[key]?.[locale] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
      return s;
    },
    [locale],
  );

  return <Ctx.Provider value={{ locale, setLocale, t }}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
