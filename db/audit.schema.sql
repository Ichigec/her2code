-- Schema for audit.db
-- Extracted: 2026-06-19T20:37:54.785808

CREATE TABLE audit_schema_version (
    version INTEGER NOT NULL
);
CREATE TABLE delegation_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_session_id TEXT NOT NULL,
    child_session_id TEXT NOT NULL UNIQUE,
    subagent_id TEXT NOT NULL,
    role TEXT NOT NULL,                    -- 'developer', 'researcher', etc.
    goal TEXT NOT NULL,
    restricted_toolset TEXT NOT NULL,      -- JSON list of allowed tools
    system_prompt TEXT,
    reason TEXT,                           -- why parent delegated this task
    max_iterations INTEGER,
    parent_turn_id TEXT,
    parent_subagent_id TEXT,
    spawn_depth INTEGER DEFAULT 1,
    created_at REAL NOT NULL               -- epoch seconds
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE INDEX idx_dc_parent ON delegation_contexts(parent_session_id);
CREATE INDEX idx_dc_child ON delegation_contexts(child_session_id);
CREATE INDEX idx_dc_role ON delegation_contexts(role);
CREATE TABLE subagent_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_session_id TEXT NOT NULL UNIQUE REFERENCES delegation_contexts(child_session_id),
    status TEXT NOT NULL,                  -- 'running', 'completed', 'timeout', 'error', 'escalated'
    started_at REAL NOT NULL,
    ended_at REAL,
    duration_ms INTEGER,
    tool_call_count INTEGER DEFAULT 0,
    api_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    estimated_cost_usd REAL,
    exit_code INTEGER,
    error_message TEXT,
    summary TEXT,                          -- self-reported summary (free-text)
    structured_report TEXT,                -- JSON: the ClaimsReport struct
    diagnostic_dump_path TEXT,             -- path to timeout diagnostic log if applicable
    parent_visible_summary TEXT            -- what the orchestrator actually saw
);
CREATE INDEX idx_ss_status ON subagent_sessions(status);
CREATE INDEX idx_ss_child ON subagent_sessions(child_session_id);
CREATE TABLE tool_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_session_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL,      -- 1, 2, 3, ... within this session
    tool_name TEXT NOT NULL,
    args_json TEXT,                        -- sanitized arguments (PII-redacted)
    result_summary TEXT,                   -- truncated result (first 2KB)
    result_hash TEXT,                      -- SHA-256 of full result for integrity
    status TEXT NOT NULL,                  -- 'success', 'error', 'timeout', 'denied'
    duration_ms INTEGER,
    turn_id TEXT,
    api_request_id TEXT,
    tool_call_id TEXT,
    receipt_signature TEXT,                -- HMAC signature (NabaOS pattern)
    created_at REAL NOT NULL
);
CREATE INDEX idx_tt_session_seq ON tool_traces(child_session_id, sequence_number);
CREATE INDEX idx_tt_tool ON tool_traces(tool_name);
CREATE TABLE tool_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_trace_id INTEGER NOT NULL REFERENCES tool_traces(id),
    tool_name TEXT NOT NULL,
    args_hash TEXT NOT NULL,               -- SHA-256 of normalized args
    result_hash TEXT NOT NULL,             -- SHA-256 of result
    signature TEXT NOT NULL,               -- HMAC-SHA256(tool_name|args_hash|result_hash|timestamp, secret)
    signed_at REAL NOT NULL,
    verified INTEGER DEFAULT 0             -- 0=pending, 1=verified, -1=failed
);
CREATE INDEX idx_tr_trace ON tool_receipts(tool_trace_id);
CREATE TABLE claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_session_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,                -- unique within session: "claim-1", etc.
    claim_type TEXT NOT NULL,              -- 'file_created', 'package_installed', etc.
    claim_spec TEXT NOT NULL,              -- JSON: type-specific claim details
    source TEXT NOT NULL,                  -- 'structured_report' or 'llm_extracted'
    extraction_confidence REAL,            -- LLM extraction confidence (if source=llm_extracted)
    created_at REAL NOT NULL,
    UNIQUE(child_session_id, claim_id)
);
CREATE INDEX idx_claims_session ON claims(child_session_id);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE TABLE verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL REFERENCES claims(id),
    child_session_id TEXT NOT NULL,
    verdict TEXT NOT NULL,                 -- 'passed', 'failed', 'uncertain'
    method TEXT NOT NULL,                  -- 'deterministic_file', 'deterministic_http', 'llm_review', etc.
    actual_value TEXT,                     -- what was actually found
    expected_value TEXT,                   -- what the claim asserted
    evidence TEXT,                         -- JSON with trace references or file paths
    duration_ms INTEGER,
    verified_at REAL NOT NULL
);
CREATE INDEX idx_ver_session ON verifications(child_session_id);
CREATE INDEX idx_ver_verdict ON verifications(verdict);
CREATE TABLE hallucination_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_session_id TEXT NOT NULL,
    hallucination_type TEXT NOT NULL,      -- 'file', 'url', 'tool_call', 'output', 'capability', 'absence'
    severity TEXT NOT NULL,                -- 'info', 'warning', 'critical'
    confidence REAL NOT NULL,              -- 0.0–1.0
    description TEXT NOT NULL,             -- human-readable explanation
    evidence_json TEXT NOT NULL,           -- JSON array of supporting evidence
    related_claim_id INTEGER REFERENCES claims(id),
    related_tool_trace_id INTEGER REFERENCES tool_traces(id),
    detected_at REAL NOT NULL,
    resolved INTEGER DEFAULT 0,            -- 0=open, 1=acknowledged, 2=false_positive, 3=escalated
    resolution_notes TEXT
);
CREATE INDEX idx_hd_session ON hallucination_detections(child_session_id);
CREATE INDEX idx_hd_severity ON hallucination_detections(severity);
CREATE INDEX idx_hd_type ON hallucination_detections(hallucination_type);
CREATE TABLE escalation_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_session_id TEXT NOT NULL,
    from_role TEXT NOT NULL,               -- role that escalated
    from_session_id TEXT NOT NULL,
    to_role TEXT NOT NULL,                 -- role escalated to
    to_session_id TEXT,                   -- NULL until escalated agent spawned
    trigger_type TEXT NOT NULL,            -- 'hallucination', 'claim_failure', 'timeout', 'confidence_low', 'error'
    trigger_detail TEXT,                  -- JSON with trigger specifics
    confidence_threshold REAL,            -- threshold that was exceeded
    actual_confidence REAL,               -- actual confidence value
    context_summary TEXT,                 -- what context was passed up
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'accepted', 'resolved', 'rejected', 'further_escalated'
    created_at REAL NOT NULL,
    resolved_at REAL
);
CREATE INDEX idx_ee_parent ON escalation_events(parent_session_id);
CREATE INDEX idx_ee_status ON escalation_events(status);
CREATE TABLE audit_summaries (
    parent_session_id TEXT PRIMARY KEY,
    total_subagents INTEGER DEFAULT 0,
    completed_subagents INTEGER DEFAULT 0,
    failed_subagents INTEGER DEFAULT 0,
    escalated_subagents INTEGER DEFAULT 0,
    total_claims INTEGER DEFAULT 0,
    passed_claims INTEGER DEFAULT 0,
    failed_claims INTEGER DEFAULT 0,
    uncertain_claims INTEGER DEFAULT 0,
    total_hallucinations INTEGER DEFAULT 0,
    critical_hallucinations INTEGER DEFAULT 0,
    total_escalations INTEGER DEFAULT 0,
    verdict TEXT,                          -- 'PASS', 'PASS WITH NOTES', 'FAIL', 'INCONCLUSIVE'
    updated_at REAL NOT NULL,
    summary_md_path TEXT                   -- path to generated markdown report
);
CREATE TABLE cross_agent_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reviewer_session_id TEXT NOT NULL,
    reviewed_session_id TEXT NOT NULL,
    review_type TEXT NOT NULL,              -- 'claim_verification', 'code_quality', 'logic_review', 'trajectory_review', 'comprehensive'
    overall_verdict TEXT NOT NULL,          -- 'approve', 'needs_work', 'reject'
    overall_score REAL,                     -- 0.0–10.0
    dimension_scores TEXT NOT NULL,         -- JSON dict
    findings_json TEXT NOT NULL,            -- JSON list of finding objects
    confidence REAL NOT NULL,              -- 0.0–1.0
    triggers_escalation INTEGER DEFAULT 0,  -- boolean 0/1
    escalation_event_id INTEGER,
    review_md_path TEXT,
    created_at REAL NOT NULL,              -- epoch seconds
    UNIQUE(reviewer_session_id, reviewed_session_id)
);
CREATE INDEX idx_car_reviewer ON cross_agent_reviews(reviewer_session_id);
CREATE INDEX idx_car_reviewed ON cross_agent_reviews(reviewed_session_id);
CREATE TABLE post_session_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    overall_quality_score REAL NOT NULL,    -- 0.0–1.0
    dimension_scores TEXT NOT NULL,         -- JSON dict
    what_went_well TEXT,                    -- JSON array of strings
    what_went_wrong TEXT,                   -- JSON array of strings
    efficiency_metrics TEXT NOT NULL,       -- JSON dict
    improvement_suggestion_count INTEGER DEFAULT 0,
    analysis_md_path TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX idx_psa_session ON post_session_analyses(session_id);
CREATE TABLE waste_detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    waste_type TEXT NOT NULL,               -- 'redundant_tool_call', 'unnecessary_operation', etc.
    description TEXT NOT NULL,
    tool_trace_ids TEXT NOT NULL,           -- JSON array of ints
    estimated_tokens_wasted INTEGER DEFAULT 0,
    estimated_cost_usd_wasted REAL DEFAULT 0.0,
    severity TEXT DEFAULT 'low',           -- 'low', 'medium', 'high'
    suggestion TEXT,
    analysis_id INTEGER,
    created_at REAL NOT NULL
);
CREATE INDEX idx_wd_session ON waste_detections(session_id);
CREATE INDEX idx_wd_waste_type ON waste_detections(waste_type);
CREATE INDEX idx_wd_severity ON waste_detections(severity);
CREATE TABLE improvement_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,                        -- NULL for cross-session
    source_type TEXT NOT NULL,              -- 'post_session_analysis', 'cross_agent_review', 'waste_detection', 'critique', 'aggregate'
    source_id INTEGER,
    suggestion_type TEXT NOT NULL,          -- 'system_prompt', 'tool_config', etc.
    description TEXT NOT NULL,
    rationale TEXT,
    expected_impact TEXT,
    actionable INTEGER DEFAULT 1,           -- boolean 0/1
    status TEXT DEFAULT 'proposed',
    accepted_at REAL,
    implemented_at REAL,
    verified_at REAL,
    rejection_reason TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX idx_is_session ON improvement_suggestions(session_id);
CREATE INDEX idx_is_status ON improvement_suggestions(status);
CREATE INDEX idx_is_suggestion_type ON improvement_suggestions(suggestion_type);
CREATE TABLE critique_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    requested_by TEXT NOT NULL,             -- 'user' or agent session_id
    status TEXT DEFAULT 'pending',
    quality_score REAL,
    issues_count INTEGER DEFAULT 0,
    suggestions_count INTEGER DEFAULT 0,
    waste_count INTEGER DEFAULT 0,
    critique_md_path TEXT,
    error_message TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX idx_cr_session ON critique_requests(session_id);
CREATE INDEX idx_cr_status ON critique_requests(status);
