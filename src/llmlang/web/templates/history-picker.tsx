          {picker?.button === @@BUTTON@@ && (
            <div className="w2-picker">
              <label htmlFor={`w2-choice-${picker.button}`}>Gespeicherten Eintrag auswählen</label>
              <NativeSelect id={`w2-choice-${picker.button}`} value={picker.selected}
                disabled={busy || picker.entries.length === 0}
                onChange={event => void loadEntry(picker, event.target.value)}>
                <NativeSelectOption value="" disabled>
                  {picker.entries.length ? "Eintrag auswählen …" : "Noch keine Einträge gespeichert"}
                </NativeSelectOption>
                {picker.entries.map(entry => (
                  <NativeSelectOption key={entry.id} value={entry.id}>
                    {entry.preview.trim() ? entry.preview.replace(/\s+/g, " ") : "(Leerer Text)"}
                    {` — ${new Date(entry.createdAt).toLocaleString("de-DE")} · `}
                    {entry.id === "legacy" ? "übernommen" : entry.id.slice(0, 8)}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
              {picker.nextCursor !== null && (
                <Button type="button" variant="outline" disabled={busy}
                  className="w1-action w1-read" onClick={() => void moreEntries(picker)}>
                  Weitere Einträge anzeigen
                </Button>
              )}
            </div>
          )}
