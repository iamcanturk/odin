// MAIN-world hook: reads X's own GraphQL responses.
//
// Why this exists: scraping the rendered DOM gives rounded, localised strings ("1,2 B"),
// and X's markup/aria-labels change constantly — which silently produced zeros. The page
// is already fetching exact integers from its private GraphQL API, so we read those
// instead and hand them to the isolated content script via postMessage.
//
// This observes traffic the page makes anyway; it issues no requests of its own.

(function () {
  const TAG = "odin-xhook";
  const MAX_PER_MESSAGE = 200;

  function toInt(v) {
    if (v == null) return null;
    const n = typeof v === "number" ? v : parseInt(String(v).replace(/[^\d]/g, ""), 10);
    return Number.isFinite(n) ? n : null;
  }

  /** Pull ODIN's shape out of a GraphQL tweet node, or null if it isn't one. */
  function extractTweet(node) {
    const legacy = node.legacy;
    if (!legacy) return null;
    // Ads are not organic performance data.
    if (legacy.promotedMetadata) return null;

    const id = node.rest_id || legacy.id_str;
    if (!id) return null;

    // note_tweet carries the untruncated body of long-form posts.
    const noteText = node.note_tweet?.note_tweet_results?.result?.text;
    const text = noteText || legacy.full_text;
    if (!text) return null;

    const handle =
      node.core?.user_results?.result?.legacy?.screen_name ||
      node.core?.user_results?.result?.core?.screen_name ||
      null;

    // views.count is only meaningful when X says it's enabled with a count.
    const views =
      node.views?.state === "EnabledWithCount" ? toInt(node.views?.count) : toInt(node.views?.count);

    return {
      id: String(id),
      text,
      author_handle: handle ? `@${handle}` : null,
      url: handle ? `https://x.com/${handle}/status/${id}` : null,
      created_at: legacy.created_at ? new Date(legacy.created_at).toISOString() : null,
      lang: legacy.lang || null,
      metrics: {
        likes: toInt(legacy.favorite_count),
        replies: toInt(legacy.reply_count),
        reposts: toInt(legacy.retweet_count),
        bookmarks: toInt(legacy.bookmark_count),
        impressions: views,
      },
    };
  }

  /** GraphQL nests tweets differently per operation, so just walk the whole payload. */
  function collect(value, out, seen, depth) {
    if (!value || typeof value !== "object" || depth > 12 || out.length >= MAX_PER_MESSAGE) return;
    if (seen.has(value)) return;
    seen.add(value);

    if (Array.isArray(value)) {
      for (const v of value) collect(v, out, seen, depth + 1);
      return;
    }

    const type = value.__typename;
    if (type === "Tweet" || type === "TweetWithVisibilityResults") {
      const node = type === "TweetWithVisibilityResults" ? value.tweet : value;
      const tweet = node && extractTweet(node);
      if (tweet) out.push(tweet);
    }

    for (const key of Object.keys(value)) collect(value[key], out, seen, depth + 1);
  }

  /** X's user objects carry the bio/name/location/url exactly, no DOM guessing needed. */
  function extractUser(node) {
    const legacy = node.legacy || {};
    const core = node.core || {};
    const handle = legacy.screen_name || core.screen_name;
    if (!handle) return null;
    const url =
      legacy.entities?.url?.urls?.[0]?.expanded_url || legacy.url || null;
    return {
      handle,
      display_name: legacy.name || core.name || null,
      bio: legacy.description || null,
      location: legacy.location || node.location?.location || null,
      website: url,
      followers: legacy.followers_count ?? null,
      following: legacy.friends_count ?? null,
      tweets: legacy.statuses_count ?? null,
    };
  }

  function collectUsers(value, out, seen, depth) {
    if (!value || typeof value !== "object" || depth > 12 || out.length >= 5) return;
    if (seen.has(value)) return;
    seen.add(value);
    if (Array.isArray(value)) {
      for (const v of value) collectUsers(v, out, seen, depth + 1);
      return;
    }
    if (value.__typename === "User") {
      const user = extractUser(value);
      if (user) out.push(user);
    }
    for (const key of Object.keys(value)) collectUsers(value[key], out, seen, depth + 1);
  }

  function publish(payload) {
    let tweets = [];
    try {
      collect(payload, tweets, new WeakSet(), 0);
    } catch {
      return;
    }
    if (!tweets.length) return;
    // Dedupe within the batch; the page often repeats the same tweet in one response.
    const byId = new Map();
    for (const t of tweets) byId.set(t.id, t);
    window.postMessage({ source: TAG, tweets: Array.from(byId.values()) }, window.location.origin);
  }

  function publishUsers(payload) {
    let users = [];
    try {
      collectUsers(payload, users, new WeakSet(), 0);
    } catch {
      return;
    }
    if (!users.length) return;
    window.postMessage({ source: TAG, users }, window.location.origin);
  }

  function isGraphQL(url) {
    return typeof url === "string" && url.includes("/i/api/graphql/");
  }

  // --- fetch ---
  const origFetch = window.fetch;
  window.fetch = function (...args) {
    const promise = origFetch.apply(this, args);
    try {
      const url = typeof args[0] === "string" ? args[0] : args[0]?.url;
      if (isGraphQL(url)) {
        promise
          .then((res) => res.clone().json())
          .then((json) => {
            publish(json);
            publishUsers(json);
          })
          .catch(() => {});
      }
    } catch {
      /* never break the page */
    }
    return promise;
  };

  // --- XMLHttpRequest ---
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url, ...rest) {
    this.__odinUrl = url;
    return origOpen.call(this, method, url, ...rest);
  };
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    if (isGraphQL(this.__odinUrl)) {
      this.addEventListener("load", () => {
        try {
          const json = JSON.parse(this.responseText);
          publish(json);
          publishUsers(json);
        } catch {
          /* not JSON, or a partial response */
        }
      });
    }
    return origSend.apply(this, args);
  };

  console.debug("[ODIN] GraphQL hook installed");
})();
