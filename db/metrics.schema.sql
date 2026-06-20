-- Schema for metrics.db
-- Extracted: 2026-06-19T20:37:55.307936

CREATE TABLE agent_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_session_id TEXT UNIQUE NOT NULL,
        parent_session_id TEXT NOT NULL,
        agent_role TEXT NOT NULL DEFAULT '',
        session_status TEXT NOT NULL DEFAULT 'completed',
        duration_ms INTEGER NOT NULL DEFAULT 0,
        total_claims INTEGER NOT NULL DEFAULT 0,
        passed_claims INTEGER NOT NULL DEFAULT 0,
        failed_claims INTEGER NOT NULL DEFAULT 0,
        uncertain_claims INTEGER NOT NULL DEFAULT 0,
        total_tool_calls INTEGER NOT NULL DEFAULT 0,
        useful_tool_calls INTEGER NOT NULL DEFAULT 0,
        wasted_tool_calls INTEGER NOT NULL DEFAULT 0,
        total_hallucinations INTEGER NOT NULL DEFAULT 0,
        critical_hallucinations INTEGER NOT NULL DEFAULT 0,
        escalation_count INTEGER NOT NULL DEFAULT 0,
        was_escalated INTEGER NOT NULL DEFAULT 0,
        input_tokens INTEGER NOT NULL DEFAULT 0,
        output_tokens INTEGER NOT NULL DEFAULT 0,
        wasted_tokens INTEGER NOT NULL DEFAULT 0,
        task_completed INTEGER NOT NULL DEFAULT 0,
        first_pass_yield INTEGER NOT NULL DEFAULT 0,
        escalation_rate_flag INTEGER NOT NULL DEFAULT 0,
        claim_accuracy REAL,
        hallucination_rate REAL,
        efficiency_ratio REAL,
        token_waste_ratio REAL,
        computed_at REAL NOT NULL DEFAULT 0.0
    );
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE metric_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_type TEXT NOT NULL,
        period_start REAL NOT NULL,
        period_end REAL NOT NULL,
        agent_role TEXT,
        total_sessions INTEGER NOT NULL DEFAULT 0,
        completed_sessions INTEGER NOT NULL DEFAULT 0,
        failed_sessions INTEGER NOT NULL DEFAULT 0,
        escalated_sessions INTEGER NOT NULL DEFAULT 0,
        total_claims INTEGER NOT NULL DEFAULT 0,
        passed_claims INTEGER NOT NULL DEFAULT 0,
        failed_claims INTEGER NOT NULL DEFAULT 0,
        total_tool_calls INTEGER NOT NULL DEFAULT 0,
        useful_tool_calls INTEGER NOT NULL DEFAULT 0,
        wasted_tool_calls INTEGER NOT NULL DEFAULT 0,
        total_hallucinations INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        wasted_tokens INTEGER NOT NULL DEFAULT 0,
        task_completion_rate REAL NOT NULL DEFAULT 0.0,
        claim_accuracy REAL NOT NULL DEFAULT 0.0,
        hallucination_rate REAL NOT NULL DEFAULT 0.0,
        efficiency_ratio REAL NOT NULL DEFAULT 0.0,
        first_pass_yield REAL NOT NULL DEFAULT 0.0,
        escalation_rate REAL NOT NULL DEFAULT 0.0,
        token_waste REAL NOT NULL DEFAULT 0.0,
        snapshot_at REAL NOT NULL DEFAULT 0.0,
        UNIQUE(period_type, period_start, agent_role)
    );
CREATE TABLE metric_trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_role TEXT,
        metric_name TEXT NOT NULL,
        current_value REAL NOT NULL DEFAULT 0.0,
        previous_value REAL NOT NULL DEFAULT 0.0,
        delta_pct REAL NOT NULL DEFAULT 0.0,
        slope REAL,
        trend TEXT NOT NULL DEFAULT 'insufficient_data',
        computed_at REAL NOT NULL DEFAULT 0.0,
        UNIQUE(agent_role, metric_name)
    );
CREATE TABLE recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_type TEXT NOT NULL,
        period_start REAL NOT NULL DEFAULT 0.0,
        target_metric TEXT NOT NULL,
        direction TEXT NOT NULL DEFAULT 'improve',
        recommendation TEXT NOT NULL DEFAULT '',
        priority TEXT NOT NULL DEFAULT 'medium',
        generated_at REAL NOT NULL DEFAULT 0.0
    );
CREATE TABLE metrics_schema_version (
        version INTEGER NOT NULL DEFAULT 1
    );
