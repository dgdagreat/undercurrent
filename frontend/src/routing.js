// Hash routing — the URL is the single source of truth for which view shows.
// Extracted from App so it can be unit-tested and reused.
//
//   #/                     -> home
//   #/about                -> about
//   #/business/12          -> a business detail
//   #/compare/3,7,12       -> compare 2-4 businesses

export function parseHash(hash = window.location.hash) {
  const biz = hash.match(/^#\/business\/(\d+)/);
  if (biz) return { view: "business", id: Number(biz[1]), ids: [] };

  const cmp = hash.match(/^#\/compare\/([\d,]+)/);
  if (cmp) {
    const ids = cmp[1]
      .split(",")
      .map((s) => Number(s))
      .filter((n) => Number.isInteger(n) && n > 0);
    return { view: "compare", id: null, ids };
  }

  if (hash.startsWith("#/about")) return { view: "about", id: null, ids: [] };
  return { view: "home", id: null, ids: [] };
}

export const hashForBusiness = (id) => `/business/${id}`;
export const hashForCompare = (ids) => `/compare/${ids.join(",")}`;
