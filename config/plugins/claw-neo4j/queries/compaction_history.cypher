MATCH (a:CompactionAction)
WHERE a.ts >= datetime() - duration({days: coalesce($since_days, 7)})
RETURN a.id AS id, a.op AS op, a.ts AS ts, a.human_gate AS human_gate, a.rationale AS rationale
ORDER BY a.ts DESC
LIMIT 50
