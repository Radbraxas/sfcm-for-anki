// SPDX-License-Identifier: AGPL-3.0-or-later
// Foundation screen: engine status, provider setup and a generation smoke test.
// The real Card Studio UI (roadmap C01) replaces the generator panel.
import { useCallback, useEffect, useRef, useState } from "react";
import { EngineError, type EngineStatus, getStatus, onStatus, request } from "./ipc/engine";
import type { Card, CardsGenerateResult, ProviderList } from "./ipc/protocol.gen";
import { type KeyService, deleteKey, hasKey, saveKey } from "./ipc/secrets";
import { describeError, describeProgress } from "./messages";

const KEY_SERVICES: KeyService[] = ["anthropic", "openai"];

function StatusPill({ status }: { status: EngineStatus }) {
  const label =
    status.state === "ready"
      ? `Engine ${status.engineVersion}`
      : status.state === "restarting"
        ? `Engine restarting (attempt ${status.attempt})`
        : status.state === "failed"
          ? "Engine stopped"
          : "Engine starting";
  return (
    <output className={`pill pill-${status.state}`} aria-live="polite">
      {label}
    </output>
  );
}

function ProviderPanel({ ready }: { ready: boolean }) {
  const [list, setList] = useState<ProviderList | null>(null);
  const [keys, setKeys] = useState<Record<string, boolean>>({});
  const [draft, setDraft] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    setList(await request("providers/list", {}));
    const entries = await Promise.all(KEY_SERVICES.map(async (s) => [s, await hasKey(s)] as const));
    setKeys(Object.fromEntries(entries));
  }, []);

  useEffect(() => {
    if (ready) refresh().catch((e) => setMessage(describeError(e)));
  }, [ready, refresh]);

  if (!list) return <section className="panel">Loading providers…</section>;
  const active = list.providers.find((p) => p.id === list.activeProvider);

  const setSetting = async (key: string, value: unknown) => {
    await request("settings/set", { key, value });
    await refresh();
  };

  return (
    <section className="panel" aria-labelledby="provider-h">
      <h2 id="provider-h">AI provider</h2>
      <label className="field">
        <span>Provider</span>
        <select
          id="provider"
          value={list.activeProvider}
          onChange={(e) => setSetting("llm.provider", e.target.value)}
        >
          {list.providers.map((p) => (
            <option key={p.id} value={p.id} disabled={p.blockedByLocalOnly}>
              {p.name}
              {p.blockedByLocalOnly ? " (blocked: local only)" : ""}
            </option>
          ))}
        </select>
      </label>
      <label className="check">
        <input
          id="local-only"
          type="checkbox"
          checked={list.localOnly}
          onChange={(e) => setSetting("llm.localOnly", e.target.checked)}
        />
        <span>Local only: never send my notes off this computer</span>
      </label>
      {active?.needsApiKey && (
        <div className="field">
          <label htmlFor="api-key">
            API key {keys[active.id] ? "(saved in your system keychain)" : "(not set)"}
          </label>
          <div className="row">
            <input
              id="api-key"
              type="password"
              autoComplete="off"
              value={draft}
              placeholder={keys[active.id] ? "Enter a new key to replace it" : "Paste your key"}
              onChange={(e) => setDraft(e.target.value)}
            />
            <button
              type="button"
              disabled={!draft}
              onClick={async () => {
                await saveKey(active.id as KeyService, draft.trim());
                setDraft("");
                setMessage("Key saved to your system keychain.");
                await refresh();
              }}
            >
              Save key
            </button>
            {keys[active.id] && (
              <button
                type="button"
                className="ghost"
                onClick={async () => {
                  await deleteKey(active.id as KeyService);
                  setMessage("Key removed.");
                  await refresh();
                }}
              >
                Remove
              </button>
            )}
          </div>
        </div>
      )}
      <div className="row">
        <button
          type="button"
          onClick={async () => {
            setMessage("Testing…");
            try {
              const r = await request("providers/test", { providerId: list.activeProvider });
              setMessage(`Connected to ${r.model} in ${r.latencyMs} ms.`);
            } catch (e) {
              setMessage(describeError(e));
            }
          }}
        >
          Test connection
        </button>
        <span className="muted">Model: {active?.defaultModel}</span>
      </div>
      {message && <p className="note">{message}</p>}
    </section>
  );
}

function CardPreview({ card }: { card: Card }) {
  return (
    <li className="card">
      <span className="tag">{card.noteType}</span>
      {card.noteType === "cloze" ? (
        <p>{card.text}</p>
      ) : (
        <>
          <p className="q">{card.front}</p>
          <p className="a">{card.back}</p>
        </>
      )}
      {card.why && <p className="muted">{card.why}</p>}
    </li>
  );
}

function GeneratePanel({ ready }: { ready: boolean }) {
  const [source, setSource] = useState("");
  const [count, setCount] = useState(8);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [result, setResult] = useState<CardsGenerateResult | null>(null);
  const controller = useRef<AbortController | null>(null);

  const run = async () => {
    controller.current = new AbortController();
    setBusy(true);
    setResult(null);
    try {
      const r = await request(
        "cards/generate",
        { source, count },
        {
          signal: controller.current.signal,
          onProgress: (p) => setProgress(describeProgress(p.message)),
        },
      );
      setResult(r);
      const cost = r.usage.costUsd == null ? "cost unknown" : `$${r.usage.costUsd.toFixed(4)}`;
      setProgress(`${r.cards.length} cards, ${r.rejected} rejected, ${cost}.`);
    } catch (e) {
      setProgress(e instanceof EngineError && e.cancelled ? "Stopped." : describeError(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-labelledby="gen-h">
      <h2 id="gen-h">Try card generation</h2>
      <label className="field">
        <span>Source text</span>
        <textarea
          id="source"
          rows={6}
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="Paste a paragraph from your notes."
        />
      </label>
      <div className="row">
        <label className="inline">
          Cards
          <input
            id="count"
            type="number"
            min={1}
            max={60}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
          />
        </label>
        {busy ? (
          <button type="button" onClick={() => controller.current?.abort()}>
            Stop
          </button>
        ) : (
          <button
            type="button"
            className="primary"
            disabled={!ready || !source.trim()}
            onClick={run}
          >
            Generate
          </button>
        )}
        <span className="muted" aria-live="polite">
          {progress}
        </span>
      </div>
      {result && (
        <ul className="cards">
          {result.cards.map((c) => (
            <CardPreview key={c.id} card={c} />
          ))}
        </ul>
      )}
    </section>
  );
}

export function App() {
  const [status, setStatus] = useState<EngineStatus>({ state: "starting" });

  useEffect(() => {
    getStatus().then(setStatus, () => {});
    const unlisten = onStatus(setStatus);
    return () => {
      unlisten.then((fn) => fn());
    };
  }, []);

  const ready = status.state === "ready";
  return (
    <main className="app">
      <header className="top">
        <h1>SFCM for Anki</h1>
        <StatusPill status={status} />
      </header>
      {status.state === "failed" && <p className="note error">{status.reason}</p>}
      <ProviderPanel ready={ready} />
      <GeneratePanel ready={ready} />
      <footer className="muted">Not affiliated with Anki or Ankitects.</footer>
    </main>
  );
}
