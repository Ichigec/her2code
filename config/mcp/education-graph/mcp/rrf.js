/**
 * Reciprocal Rank Fusion (RRF) — shared utility for hybrid search.
 *
 * Generic function: fuses any number of ranked result lists into a single ranking.
 * Each result item must have an `id` field.
 *
 * Algorithm: score = Σ weight_i / (K + rank_i), where K=60 (standard).
 *
 * Used by:
 *   - search.js (claw graph: BM25 + Cosine hybrid search)
 *   - education-server.mjs (education graph: BM25 + Cosine search)
 *   - codebase-server.mjs (codebase graph: BM25 + Cosine hybrid search)
 *
 * @param {Array<{id: string, results: Array<{id: string}>}>} rankedLists
 *   Array of ranked lists. Each entry: { id: "list_name", results: [{id: "entity_id"}, ...] }
 * @param {Object} [opts]
 * @param {number} [opts.topK=20] - Number of top results to return
 * @param {number} [opts.K=60] - RRF constant (standard: 60)
 * @param {number[]} [opts.weights] - Weight per list (default: equal weights 1/N)
 * @returns {Array<[string, number]>} - Array of [id, rrf_score] sorted descending by score
 *
 * @example
 * // Fuse BM25 and cosine results with custom weights
 * rrfFuse([
 *   { id: "bm25", results: [{id: "a"}, {id: "b"}] },
 *   { id: "cosine", results: [{id: "b"}, {id: "a"}] }
 * ], { topK: 10, weights: [0.3, 0.7] });
 * // => [["b", 0.0166...], ["a", 0.0164...]]
 */
export function rrfFuse(rankedLists, opts = {}) {
  const { K = 60, topK = 20 } = opts;
  const weights =
    opts.weights ?? rankedLists.map(() => 1.0 / rankedLists.length);
  const scores = new Map();

  for (let i = 0; i < rankedLists.length; i++) {
    const weight = weights[i];
    const results = rankedLists[i].results;
    for (let rank = 0; rank < results.length; rank++) {
      const id = results[rank].id;
      scores.set(id, (scores.get(id) || 0) + weight / (K + rank));
    }
  }

  return Array.from(scores.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, topK);
}

/**
 * Convenience wrapper for the classic two-list BM25+Cosine fusion.
 * Preserves backward compatibility with existing callers.
 *
 * @param {Array<{id: string}>} bm25Results - BM25-ranked results
 * @param {Array<{id: string}>} cosineResults - Cosine-ranked results
 * @param {number} [topK=20] - Top results to return
 * @param {number} [bm25Weight=0.3] - Weight for BM25 (cosine = 1 - bm25Weight)
 * @returns {Array<[string, number]>}
 */
export function reciprocalRankFusion(
  bm25Results,
  cosineResults,
  topK = 20,
  bm25Weight = 0.3,
) {
  const cosineWeight = 1 - bm25Weight;
  return rrfFuse(
    [
      { id: "bm25", results: bm25Results },
      { id: "cosine", results: cosineResults },
    ],
    { topK, weights: [bm25Weight, cosineWeight] },
  );
}
