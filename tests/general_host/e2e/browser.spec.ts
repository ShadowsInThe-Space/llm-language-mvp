import {randomUUID} from "node:crypto";
import {expect, test, type Page, type TestInfo} from "@playwright/test";

const APPS = [
  {name: "history", heading: "Saved text history"},
  {name: "tasks", heading: "Task planner"},
] as const;
const TEXT_LABEL = "Text (first 120 characters saved)";

function identifier(info: TestInfo, suffix: string): string {
  return `e2e-${Date.now()}-${info.project.name}-${suffix}-${randomUUID().slice(0, 6)}`;
}

function titleFor(id: string): string {
  return `${id} ${"😀é漢x".repeat(40)}`;
}

function preview(title: string): string {
  return Array.from(title).slice(0, 120).join("");
}

function panels(page: Page) {
  return {
    create: page.getByRole("region", {name: "create", exact: true}),
    listing: page.getByRole("region", {name: "listing", exact: true}),
    detail: page.getByRole("region", {name: "detail", exact: true}),
    edit: page.getByRole("region", {name: "edit", exact: true}),
  };
}

function apiResponse(page: Page, app: string, action: string) {
  return page.waitForResponse(response =>
    new URL(response.url()).pathname === `/api/${app}` &&
    response.request().method() === "POST" &&
    response.request().postDataJSON()?.action === action,
  );
}

async function frames(page: Page): Promise<void> {
  await page.evaluate(() => new Promise<void>(resolve =>
    requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
  ));
}

async function save(page: Page, app: string, id: string, title: string, keyboard = false) {
  const {create} = panels(page);
  const key = create.getByLabel("Identifier", {exact: true});
  const text = create.getByLabel(TEXT_LABEL, {exact: true});
  await expect(create.getByRole("button", {name: "Save", exact: true})).toBeEnabled();
  await key.fill(id);
  await text.fill(title);
  const response = apiResponse(page, app, "save");
  if (keyboard) {
    await key.focus();
    await page.keyboard.press("Tab");
    await expect(text).toBeFocused();
    await page.keyboard.press("Enter");
  } else {
    await create.getByRole("button", {name: "Save", exact: true}).click();
  }
  expect((await response).status()).toBe(200);
  await expect(create.getByRole("status")).toHaveText("Saved");
  await expect(create.getByRole("definition")).toContainText([id, preview(title)]);
}

async function promoteTask(page: Page, id: string, title: string) {
  const edit = panels(page).edit;
  await edit.getByLabel("Task identifier", {exact: true}).fill(id);
  await edit.getByLabel("Title (first 120 characters saved)", {exact: true}).fill(title);
  await edit.getByLabel("Expected revision", {exact: true}).fill("0");
  await edit.getByLabel("Completed", {exact: true}).check();
  await edit.getByLabel("Priority", {exact: true}).fill(String(Date.now()));
  const response = apiResponse(page, "tasks", "update");
  await edit.getByRole("button", {name: "Update task", exact: true}).click();
  expect((await response).status()).toBe(200);
  await expect(edit.getByRole("status")).toHaveText("Updated");
  await expect(edit.getByRole("definition")).toContainText([id, preview(title), "1", "Yes"]);
}

async function loadAndSelect(page: Page, app: string, id: string, title: string) {
  const {listing, detail} = panels(page);
  const load = apiResponse(page, app, "browse");
  await listing.getByRole("button", {name: "Load", exact: true}).click();
  expect((await load).status()).toBe(200);
  await expect(listing.getByRole("status")).toHaveText("Entries loaded");
  const row = listing.getByRole("row").filter({hasText: preview(title)});
  await expect(row).toHaveCount(1);
  const selected = apiResponse(page, app, "fetch");
  await row.getByRole("button", {name: /^Select /}).click();
  expect((await selected).status()).toBe(200);
  await expect(detail.getByRole("status")).toHaveText("Selection loaded");
  await expect(detail.getByRole("cell", {name: id, exact: true})).toBeVisible();
  await expect(detail.getByRole("cell", {name: preview(title), exact: true})).toBeVisible();
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(done => {resolve = done;});
  return {promise, resolve: () => resolve()};
}

for (const app of APPS) {
  test(`${app.name}: accessible click/keyboard save, real D1 list/detail, clear and reload`,
    async ({page}, info) => {
      let writes = 0;
      page.on("request", request => {
        if (request.method() === "POST" &&
            new URL(request.url()).pathname === `/api/${app.name}`) writes += 1;
      });
      await page.goto(`/${app.name}`);
      await expect(page.getByRole("heading", {level: 1, name: app.heading})).toBeVisible();
      const clicked = identifier(info, "click");
      await save(page, app.name, clicked, titleFor(clicked));
      const id = identifier(info, "key");
      const title = titleFor(id);
      expect(Array.from(title).length).toBeGreaterThan(120);
      expect(Buffer.byteLength(title)).toBeLessThanOrEqual(512);
      await save(page, app.name, id, title, true);
      if (app.name === "tasks") await promoteTask(page, id, title);
      await loadAndSelect(page, app.name, id, title);
      const beforeClear = writes;
      await panels(page).create.getByRole("button", {name: "Clear display", exact: true}).click();
      await expect(panels(page).create.getByRole("status")).toHaveText("No saved value");
      await expect(panels(page).create.getByRole("definition")).toHaveCount(0);
      await frames(page);
      expect(writes).toBe(beforeClear);
      await page.reload();
      await expect(panels(page).listing.getByRole("button", {name: "Load"})).toBeEnabled();
      await expect(panels(page).listing.getByRole("status")).toHaveText("No entries");
      await loadAndSelect(page, app.name, id, title);
    });

  test(`${app.name}: transport failure retains the last confirmed saved value`,
    async ({page}, info) => {
      await page.goto(`/${app.name}`);
      const confirmed = identifier(info, "ok");
      const title = titleFor(confirmed);
      await save(page, app.name, confirmed, title);
      const create = panels(page).create;
      await create.getByLabel("Identifier", {exact: true}).fill(identifier(info, "fail"));
      await create.getByLabel(TEXT_LABEL, {exact: true}).fill("Unconfirmed replacement");
      await page.route(`**/api/${app.name}`, async route => {
        if (route.request().postDataJSON()?.action === "save") {
          await route.fulfill({status: 503, contentType: "application/json",
            body: JSON.stringify({error: "ServiceUnavailable"})});
        } else {
          await route.continue();
        }
      });
      await create.getByRole("button", {name: "Save", exact: true}).click();
      await expect(create.getByRole("alert")).toHaveText("Save failed");
      await expect(create.getByRole("definition")).toContainText([confirmed, preview(title)]);
    });

  test(`${app.name}: an older real detail response cannot replace the newer selection`,
    async ({page, request, baseURL}, info) => {
      const origin = new URL(baseURL ?? "http://127.0.0.1:8787").origin;
      const ids = [identifier(info, "first"), identifier(info, "second")];
      const titles = ids.map(titleFor);
      for (const [index, id] of ids.entries()) {
        const saved = await request.post(`/api/${app.name}`, {headers: {origin}, data: {
          action: "save", input: {record: "saveInput", fields: {id, title: titles[index]}},
        }});
        expect(saved.status()).toBe(200);
        if (app.name === "tasks") {
          const changed = await request.post("/api/tasks", {headers: {origin}, data: {
            action: "update", input: {record: "updateInput", fields: {id, title: titles[index],
              revision: "0", done: false, priority: String(Date.now() + index)}},
          }});
          expect(changed.status()).toBe(200);
        }
      }
      await page.goto(`/${app.name}`);
      await expect(panels(page).listing.getByRole("button", {name: "Load"})).toBeEnabled();
      const listing = apiResponse(page, app.name, "browse");
      await panels(page).listing.getByRole("button", {name: "Load"}).click();
      expect((await listing).status()).toBe(200);
      const firstReady = deferred();
      const releaseFirst = deferred();
      const firstFinished = deferred();
      let firstStatus: number | undefined;
      await page.route(`**/api/${app.name}`, async route => {
        const data = route.request().postDataJSON();
        if (data?.action !== "fetch" || data?.input?.fields?.selected_id !== ids[0]) {
          await route.continue();
          return;
        }
        try {
          // Fetch genuine D1 data, delaying delivery rather than inventing a row.
          const response = await route.fetch();
          firstStatus = response.status();
          firstReady.resolve();
          await releaseFirst.promise;
          // Aborting an obsolete browser request can make delivery fail normally.
          await route.fulfill({response}).catch(() => undefined);
        } finally {
          firstReady.resolve();
          firstFinished.resolve();
        }
      });
      try {
        const first = panels(page).listing.getByRole("row").filter({hasText: preview(titles[0])});
        await first.getByRole("button", {name: /^Select /}).click();
        await firstReady.promise;
        expect(firstStatus).toBe(200);
        const secondResponse = apiResponse(page, app.name, "fetch");
        const second = panels(page).listing.getByRole("row").filter({hasText: preview(titles[1])});
        await second.getByRole("button", {name: /^Select /}).click();
        expect((await secondResponse).status()).toBe(200);
        await expect(panels(page).detail.getByRole("cell", {name: ids[1], exact: true})).toBeVisible();
        releaseFirst.resolve();
        await firstFinished.promise;
        await frames(page);
        await expect(panels(page).detail.getByRole("cell", {name: ids[1], exact: true})).toBeVisible();
        await expect(panels(page).detail.getByRole("cell", {name: ids[0], exact: true})).toHaveCount(0);
      } finally {
        releaseFirst.resolve();
      }
    });

  test(`${app.name}: SSR controls are inert until delayed real hydration completes`,
    async ({page}, info) => {
      const scripts = deferred();
      let blocked = 0;
      let posts = 0;
      page.on("request", request => {
        if (request.method() === "POST" &&
            new URL(request.url()).pathname === `/api/${app.name}`) posts += 1;
      });
      await page.route("**/*", async route => {
        if (route.request().resourceType() === "script") {
          blocked += 1;
          await scripts.promise;
        }
        await route.continue();
      });
      try {
        await page.goto(`/${app.name}`, {waitUntil: "commit"});
        const create = panels(page).create;
        await expect(create).toBeVisible();
        await expect.poll(() => blocked).toBeGreaterThan(0);
        const controls = page.getByRole("main").locator("input,select,button");
        for (let index = 0; index < await controls.count(); index += 1) {
          await expect(controls.nth(index)).toBeDisabled();
        }
        const location = page.url();
        await create.getByRole("button", {name: "Save", exact: true})
          .evaluate(button => (button as HTMLButtonElement).click());
        await frames(page);
        expect(page.url()).toBe(location);
        expect(posts).toBe(0);
      } finally {
        scripts.resolve();
      }
      await expect(panels(page).create.getByRole("button", {name: "Save", exact: true}))
        .toBeEnabled();
      const id = identifier(info, "hydrated");
      await save(page, app.name, id, titleFor(id));
    });
}
