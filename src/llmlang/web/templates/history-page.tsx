@@SUPPORT@@
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";

type Entry = { id: string; preview: string; createdAt: string };
type OutputSetter = (result: ConfirmedValue | null) => void;
type Picker = {
  button: string; slot: string; maxBytes: number; setOutput: OutputSetter;
  entries: Entry[]; nextCursor: string | null; selected: string;
};

function newRequestKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

function entryPage(payload: unknown): {entries: Entry[]; nextCursor: string | null} {
  if (typeof payload !== "object" || payload === null || !("entries" in payload)
    || !Array.isArray(payload.entries) || payload.entries.length > 20
    || !("nextCursor" in payload) || !(payload.nextCursor === null
      || typeof payload.nextCursor === "string" && /^[1-9][0-9]{0,14}$/.test(payload.nextCursor))) {
    throw new Error("Invalid entry list");
  }
  const entries = payload.entries.map((entry: unknown) => {
    if (typeof entry !== "object" || entry === null || !("id" in entry)
      || typeof entry.id !== "string" || !/^(legacy|[0-9a-f-]{36})$/.test(entry.id)
      || !("preview" in entry) || typeof entry.preview !== "string"
      || !validText(entry.preview, 4096) || Array.from(entry.preview).length > 80
      || !("createdAt" in entry) || typeof entry.createdAt !== "string"
      || !Number.isFinite(Date.parse(entry.createdAt))) throw new Error("Invalid entry");
    return {id: entry.id, preview: entry.preview, createdAt: entry.createdAt};
  });
  return {entries, nextCursor: payload.nextCursor};
}

export default function Page() {
  const clientReady = useSyncExternalStore(subscribeToClient, clientSnapshot, serverSnapshot);
@@STATES@@
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Bereit. Jeder gespeicherte Text bleibt als Eintrag erhalten.");
  const [error, setError] = useState<string | null>(null);
  const [picker, setPicker] = useState<Picker | null>(null);
  const inFlight = useRef(false);
  const completedReads = useRef(0);
  const writeAttempt = useRef<{slot: string; value: string; key: string} | null>(null);

  async function perform(message: string, operation: (signal: AbortSignal) => Promise<void>) {
    if (!clientReady || inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    setStatus(message);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      await operation(controller.signal);
    } catch {
      setError(controller.signal.aborted ? "Die Anfrage dauert zu lange. Bitte erneut versuchen."
        : "Die Aktion konnte nicht bestätigt werden. Bitte erneut versuchen.");
      setStatus("Letzte bestätigte Anzeige bleibt erhalten.");
    } finally {
      clearTimeout(timer);
      inFlight.current = false;
      setBusy(false);
    }
  }

  async function request(slot: string, query: string, signal: AbortSignal, init?: RequestInit) {
    const response = await fetch(`/api/store/${encodeURIComponent(slot)}${query}`, {
      credentials: "same-origin", cache: "no-store", ...init, signal,
    });
    if (!response.ok) throw new Error("Request failed");
    return await response.json() as unknown;
  }

  function confirm(result: StoredValue, effect: "read" | "write", setOutput: OutputSetter) {
    const time = new Date().toLocaleTimeString("de-DE", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
    const receipt = effect === "read"
      ? `Aus der Datenbank geladen · Abruf #${++completedReads.current} · ${time} Uhr`
      : `Neuer Eintrag gespeichert · ${time} Uhr`;
    setOutput({...result, receipt});
    setStatus(effect === "read" ? "Aus der Datenbank geladen." : "Neuer Eintrag gespeichert.");
  }

  async function invoke(slot: string, effect: "read" | "write", value: string | null,
    maxBytes: number, setOutput: OutputSetter) {
    if (effect !== "write" || value === null || !validText(value, maxBytes)) {
      setError(`Bitte gültigen Text mit höchstens ${maxBytes} Bytes eingeben.`);
      return;
    }
    await perform("Wird gespeichert …", async signal => {
      if (writeAttempt.current?.slot !== slot || writeAttempt.current?.value !== value) {
        writeAttempt.current = {slot, value, key: newRequestKey()};
      }
      const result = storedValue(await request(slot, "", signal, {
        method: "POST", headers: {"Content-Type": "application/json",
          "Idempotency-Key": writeAttempt.current.key}, body: JSON.stringify({value}),
      }), maxBytes);
      if (!result.found || result.value !== value) throw new Error("Invalid save confirmation");
      writeAttempt.current = null;
      setPicker(null);
      confirm(result, "write", setOutput);
    });
  }

  async function openPicker(slot: string, maxBytes: number, setOutput: OutputSetter, button: string) {
    await perform("Gespeicherte Einträge werden geladen …", async signal => {
      const page = entryPage(await request(slot, "?entries=1", signal));
      setPicker({slot, maxBytes, setOutput, button, ...page, selected: ""});
      setStatus(page.entries.length ? "Bitte einen Eintrag auswählen." : "Noch keine Einträge gespeichert.");
    });
  }

  async function moreEntries(current: Picker) {
    if (current.nextCursor === null) return;
    await perform("Weitere Einträge werden geladen …", async signal => {
      const page = entryPage(await request(current.slot,
        `?entries=1&before=${encodeURIComponent(current.nextCursor!)}`, signal));
      const entries = [...new Map([...current.entries, ...page.entries].map(entry => [entry.id, entry])).values()];
      setPicker({...current, entries, nextCursor: page.nextCursor});
      setStatus("Weitere Einträge geladen. Bitte auswählen.");
    });
  }

  async function loadEntry(current: Picker, id: string) {
    if (!current.entries.some(entry => entry.id === id)) return;
    await perform("Eintrag wird aus der Datenbank geladen …", async signal => {
      const result = storedValue(await request(current.slot, `?id=${encodeURIComponent(id)}`, signal), current.maxBytes);
      if (!result.found) throw new Error("Entry missing");
      setPicker({...current, selected: id});
      confirm(result, "read", current.setOutput);
    });
  }

  function clearOutput(setOutput: OutputSetter) {
    if (!clientReady || inFlight.current) return;
    setOutput(null);
    setPicker(null);
    setError(null);
    setStatus("Anzeige geleert. Alle Einträge bleiben in der Datenbank gespeichert.");
  }

  return (
    <main className="w1-shell">
      <section className="w1-workspace" aria-labelledby="w1-title">
        <header className="w1-header">
          <span className="w1-mark" aria-hidden="true" />
          <h1 id="w1-title">{@@TITLE@@}</h1>
          <p>Texte speichern, einen Eintrag auswählen und wieder abrufen.</p>
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
