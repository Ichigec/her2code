/**
 * OpenCode plugin: every `interval` agent steps, send the last `historySize`
 * steps to a reviewer LLM and inject its feedback into the next turn.
 */

const DEFAULTS = {
  interval: 10,
  historySize: 30,
  model: "qwen3.6-35b-heretic",
  baseURL: process.env.OPENAI_BASE_URL || "http://127.0.0.1:4000/v1",
  apiKey:
    process.env.OPENAI_API_KEY ||
    process.env.LITELLM_API_KEY ||
    process.env.OPENCODE_LLM_API_KEY ||
    "sk-local",
  maxOutputTokens: 1024,
};

function parseModel(spec) {
  const s = String(spec || DEFAULTS.model);
  const slash = s.indexOf("/");
  return slash >= 0 ? s.slice(slash + 1) : s;
}

function truncate(value, max = 400) {
  const s = value == null ? "" : String(value);
  return s.length <= max ? s : `${s.slice(0, max)}…`;
}

function summarizeArgs(args) {
  if (args == null) return "";
  if (typeof args === "string") return truncate(args, 160);
  try {
    return truncate(JSON.stringify(args), 160);
  } catch {
    return truncate(String(args), 160);
  }
}

function formatStepHistory(steps) {
  return steps
    .map((step) => {
      const tools =
        step.tools.length === 0
          ? "  (no tools)"
          : step.tools
              .map(
                (t) =>
                  `  - ${t.tool}(${summarizeArgs(t.args)}) => ${truncate(t.output, 200)}`,
              )
              .join("\n");
      return `Step ${step.index}:\n${tools}`;
    })
    .join("\n\n");
}

function mergeConfig(opts = {}) {
  return { ...DEFAULTS, ...opts };
}

function getSession(sessions, sessionID) {
  if (!sessions.has(sessionID)) {
    sessions.set(sessionID, {
      stepCount: 0,
      history: [],
      currentTools: [],
      pendingReview: null,
      reviewing: false,
    });
  }
  return sessions.get(sessionID);
}

async function runReview(sessionID, state, config) {
  if (state.reviewing) return;
  state.reviewing = true;
  try {
    const hist = state.history.slice(-config.historySize);
    const prompt = [
      "You are an agent supervisor reviewing a coding agent's recent work.",
      "",
      `The agent just completed step ${state.stepCount}.`,
      `Review the last ${hist.length} steps below.`,
      "",
      "Answer concisely in this structure:",
      "1. **Progress** — real progress or stuck in a loop?",
      "2. **Issues** — repeated actions, wrong approach, missing intent?",
      "3. **Recommendation** — specific next actions for the agent.",
      "4. **Verdict** — OK | CAUTION | STUCK",
      "",
      "Steps log:",
      formatStepHistory(hist),
    ].join("\n");

    const url = `${String(config.baseURL).replace(/\/$/, "")}/chat/completions`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({
        model: parseModel(config.model),
        max_tokens: config.maxOutputTokens,
        temperature: 0.2,
        messages: [
          {
            role: "system",
            content:
              "You review coding-agent traces. Be direct, actionable, and brief.",
          },
          { role: "user", content: prompt },
        ],
      }),
    });

    if (!res.ok) {
      const err = await res.text();
      state.pendingReview = `[step-reviewer] Review failed (${res.status}): ${truncate(err, 300)}`;
      return;
    }

    const data = await res.json();
    const text =
      data.choices?.[0]?.message?.content?.trim() || "(empty reviewer response)";
    state.pendingReview = [
      `[Step reviewer @ step ${state.stepCount}]`,
      "",
      text,
      "",
      "Apply the recommendation above before continuing.",
    ].join("\n");
    console.log(
      `[step-reviewer] session=${sessionID} step=${state.stepCount} review ready`,
    );
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    state.pendingReview = `[step-reviewer] Review error: ${msg}`;
    console.error(`[step-reviewer] session=${sessionID} error: ${msg}`);
  } finally {
    state.reviewing = false;
  }
}

export default {
  id: "step-reviewer",
  server: async (_ctx, opts) => {
    const config = mergeConfig(opts);
    /** @type {Map<string, ReturnType<typeof getSession>>} */
    const sessions = new Map();

    console.log(
      `[step-reviewer] loaded interval=${config.interval} history=${config.historySize} model=${parseModel(config.model)}`,
    );

    return {
      event: async ({ event }) => {
        if (event.type === "session.next.step.started") {
          getSession(sessions, event.properties.sessionID).currentTools = [];
          return;
        }
        if (event.type !== "session.next.step.ended") return;

        const sessionID = event.properties.sessionID;
        const state = getSession(sessions, sessionID);
        state.stepCount += 1;
        state.history.push({
          index: state.stepCount,
          tools: [...state.currentTools],
        });
        if (state.history.length > config.historySize) {
          state.history.splice(0, state.history.length - config.historySize);
        }
        state.currentTools = [];

        if (state.stepCount % config.interval === 0) {
          void runReview(sessionID, state, config);
        }
      },

      "tool.execute.after": async (input, output) => {
        const state = getSession(sessions, input.sessionID);
        state.currentTools.push({
          tool: input.tool,
          args: input.args,
          output: output.output,
        });
      },

      "experimental.chat.system.transform": async (input, output) => {
        const sessionID = input.sessionID;
        if (!sessionID) return;
        const state = sessions.get(sessionID);
        if (!state?.pendingReview) return;
        output.system.push(state.pendingReview);
        state.pendingReview = null;
      },
    };
  },
};
