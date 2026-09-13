"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type StoredValue = { found: false } | { found: true; value: string };
type ConfirmedValue = StoredValue & { receipt: string };

const clientSnapshot = () => true;
const serverSnapshot = () => false;
const subscribeToClient = () => () => {};

function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

function validText(value: string, maxBytes: number): boolean {
  return !value.includes("\u0000") && !/[\uD800-\uDFFF]/u.test(value)
    && byteLength(value) <= maxBytes;
}

function storedValue(payload: unknown, maxBytes: number): StoredValue {
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    throw new Error("Invalid response");
  }
  if ("found" in payload && payload.found === false && Object.keys(payload).length === 1) {
    return { found: false };
  }
  if ("found" in payload && payload.found === true && "value" in payload
      && typeof payload.value === "string" && validText(payload.value, maxBytes)
      && Object.keys(payload).length === 2) {
    return { found: true, value: payload.value };
  }
  throw new Error("Invalid response");
}

export default function Page() {
  const clientReady = useSyncExternalStore(subscribeToClient, clientSnapshot, serverSnapshot);
@@STATES@@
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Bereit.");
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const completedReads = useRef(0);

  async function invoke(
    slot: string,
    effect: "read" | "write",
    value: string | null,
    maxBytes: number,
    setOutput: (result: ConfirmedValue) => void,
  ): Promise<void> {
    if (!clientReady || inFlight.current) return;
    if (effect === "write" && (value === null || !validText(value, maxBytes))) {
      setError(`Bitte gültigen Text mit höchstens ${maxBytes} Bytes eingeben.`);
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setStatus(effect === "write" ? "Wird gespeichert …" : "Wird geladen …");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`/api/store/${encodeURIComponent(slot)}`, {
        method: effect === "write" ? "PUT" : "GET",
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
        ...(effect === "write" ? {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ value }),
        } : {}),
      });
      if (!response.ok) throw new Error("Request failed");
      const payload: unknown = await response.json();
      const result = storedValue(payload, maxBytes);
      if (effect === "write" && (!result.found || result.value !== value)) {
        throw new Error("Invalid write confirmation");
      }
      const time = new Date().toLocaleTimeString("de-DE", {
        hour: "2-digit", minute: "2-digit", second: "2-digit",
      });
      const receipt = effect === "read"
        ? `${result.found ? "Aus der Datenbank geladen" : "Datenbank geprüft"}`
          + ` · Abruf #${++completedReads.current} · ${time} Uhr`
        : `Speichern bestätigt · ${time} Uhr`;
      setOutput({ ...result, receipt });
      setStatus(effect === "write" ? "Gespeichert."
        : result.found ? "Aus der Datenbank geladen." : "Noch nichts gespeichert.");
    } catch {
      setError(controller.signal.aborted
        ? "Die Anfrage dauert zu lange. Bitte erneut versuchen."
        : "Die Aktion konnte nicht bestätigt werden. Bitte erneut versuchen.");
      setStatus("Bereit für einen neuen Versuch.");
    } finally {
      clearTimeout(timeout);
      inFlight.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="w1-shell">
      <section className="w1-workspace" aria-labelledby="w1-title">
        <header className="w1-header">
          <span className="w1-mark" aria-hidden="true" />
          <h1 id="w1-title">{@@TITLE@@}</h1>
          <p>Text eingeben, speichern und wieder abrufen.</p>
        </header>
        <div className="w1-widgets" aria-busy={!clientReady || busy}>
@@WIDGETS@@
        </div>
        <footer className="w1-feedback">
          <p role="status" className="w1-status">{clientReady ? status : "Wird geladen …"}</p>
          {error !== null && <p role="alert" className="w1-error">{error}</p>}
        </footer>
      </section>
    </main>
  );
}
