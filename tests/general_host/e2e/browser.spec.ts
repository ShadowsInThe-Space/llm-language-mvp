import {randomUUID} from "node:crypto";
import {expect, test, type Page, type TestInfo} from "@playwright/test";

const APPS = [
  {name: "history", heading: "Saved text history"},
  {name: "tasks", heading: "Task planner"},
] as const;

function identifier(info: TestInfo, suffix: string): string {
  // History sorts descending by ID; fresh z-prefixed records precede older seeds.
  return `z-${Date.now()}-${info.project.name}-${suffix}-${randomUUID().slice(0, 6)}`;
}

function titleFor(id: string): string {
  return `${id}\n${"😀é漢x\n".repeat(200)}End of full text`;
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

async function save(page: Page, app: string, id: string, title: string,
                    keyboard = false, confirmation = 1) {
  const {create} = panels(page);
  const key = create.getByLabel("Identifier", {exact: true});
  const text = create.getByLabel("Text", {exact: true});
  const submit = create.getByRole("button", {name: "Save", exact: true});
  await expect(submit).toBeEnabled();
  await expect(text).toHaveJSProperty("tagName", "TEXTAREA");
  await key.fill(id);
  await text.fill(title);
  const response = apiResponse(page, app, "save");
  if (keyboard) {
    await key.focus();
    await page.keyboard.press("Tab");
    await expect(text).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(submit).toBeFocused();
    await page.keyboard.press("Enter");
  } else {
    await submit.click();
  }
  expect((await response).status()).toBe(200);
  await expect(create.getByRole("status"))
    .toHaveText(`Saved · Confirmation ${confirmation}`);
  await expect(create.getByRole("definition").nth(0)).toHaveText(id);
  // textContent compares exact Unicode and line breaks, without whitespace folding.
  expect(await create.getByRole("definition").nth(1).textContent()).toBe(title);
}

async function promoteTask(page: Page, id: string, title: string, confirmation = 1) {
  const edit = panels(page).edit;
  await edit.getByLabel("Task identifier", {exact: true}).fill(id);
  await edit.getByLabel("Title", {exact: true}).fill(title);
  await edit.getByLabel("Expected revision", {exact: true}).fill("0");
  await edit.getByLabel("Completed", {exact: true}).check();
  await edit.getByLabel("Priority", {exact: true}).fill(String(Date.now()));
  const response = apiResponse(page, "tasks", "update");
  await edit.getByRole("button", {name: "Update task", exact: true}).click();
  expect((await response).status()).toBe(200);
  await expect(edit.getByRole("status"))
    .toHaveText(`Updated · Confirmation ${confirmation}`);
  await expect(edit.getByRole("definition")).toContainText([id, title, "1", "Yes"]);
  expect(await edit.getByRole("definition").nth(1).textContent()).toBe(title);
}

async function load(page: Page, app: string) {
  const response = apiResponse(page, app, "browse");
  await panels(page).listing.getByRole("button", {name: "Load", exact: true}).click();
  expect((await response).status()).toBe(200);
  await expect(panels(page).listing.getByRole("status"))
    .toHaveText("Entries loaded · Confirmation 1");
}

async function turnPage(page: Page, app: string, direction: "Next" | "Previous",
                        pageNumber: number, confirmation: number) {
  const listing = panels(page).listing;
  const action = direction === "Previous" && pageNumber === 1 ? "browse" : "browse_next";
  const response = apiResponse(page, app, action);
  await listing.getByRole("button", {name: direction, exact: true}).click();
  expect((await response).status()).toBe(200);
  await expect(listing.getByText(`Page ${pageNumber}`, {exact: true})).toBeVisible();
  await expect(listing.getByRole("status"))
    .toHaveText(`Entries loaded · Confirmation ${confirmation}`);
}

async function select(page: Page, app: string, id: string, title: string, confirmation = 1) {
  const {listing, detail} = panels(page);
  const row = listing.getByRole("row").filter({hasText: id});
  await expect(row).toHaveCount(1);
  await expect(listing.locator("tbody tr")).toHaveCount(1);
  expect(await row.getByRole("cell").nth(0).textContent()).toBe(title);
  const response = apiResponse(page, app, "fetch");
  await row.getByRole("button", {name: /^Select /}).click();
  expect((await response).status()).toBe(200);
  await expect(detail.getByRole("status"))
    .toHaveText(`Selection loaded · Confirmation ${confirmation}`);
  await expect(detail.getByRole("cell", {name: id, exact: true})).toBeVisible();
  expect(await detail.getByRole("cell").nth(1).textContent()).toBe(title);
}

function deferred() {
  let resolve!: () => void;
  const promise = new Promise<void>(done => {resolve = done;});
  return {promise, resolve: () => resolve()};
}

for (const app of APPS) {
  test(`${app.name}: full text, keyboard/click save, real D1 paging, clear and reload`,
    async ({page}, info) => {
      let requests = 0;
      page.on("request", request => {
        if (request.method() === "POST" &&
            new URL(request.url()).pathname === `/api/${app.name}`) requests += 1;
      });
      await page.goto(`/${app.name}`);
      await expect(page.getByRole("heading", {level: 1, name: app.heading})).toBeVisible();
      const oldest = identifier(info, "click");
      const oldestTitle = titleFor(oldest);
      await save(page, app.name, oldest, oldestTitle);
      if (app.name === "tasks") await promoteTask(page, oldest, oldestTitle);
      const newest = identifier(info, "key");
      const newestTitle = titleFor(newest);
      expect(Array.from(newestTitle).length).toBeGreaterThan(120);
      expect(Buffer.byteLength(newestTitle)).toBeGreaterThan(512);
      expect(Buffer.byteLength(newestTitle)).toBeLessThanOrEqual(4096);
      await save(page, app.name, newest, newestTitle, true, 2);
      if (app.name === "tasks") await promoteTask(page, newest, newestTitle, 2);
      await load(page, app.name);
      await select(page, app.name, newest, newestTitle);
      await turnPage(page, app.name, "Next", 2, 2);
      await select(page, app.name, oldest, oldestTitle, 2);
      await turnPage(page, app.name, "Previous", 1, 3);
      await select(page, app.name, newest, newestTitle, 3);
      const beforeClear = requests;
      await panels(page).create.getByRole("button", {name: "Clear display", exact: true}).click();
      await expect(panels(page).create.getByRole("status"))
        .toHaveText("No saved value");
      await expect(panels(page).create.getByRole("definition")).toHaveCount(0);
      await frames(page);
      expect(requests).toBe(beforeClear);
      await page.reload();
      await expect(panels(page).listing.getByRole("button", {name: "Load"})).toBeEnabled();
      await expect(panels(page).listing.getByRole("status")).toHaveText("No entries");
      await load(page, app.name);
      await select(page, app.name, newest, newestTitle);
    });

  test(`${app.name}: transport failure retains the last confirmed saved value`,
    async ({page}, info) => {
      await page.goto(`/${app.name}`);
      const confirmed = identifier(info, "ok");
      const title = titleFor(confirmed);
      await save(page, app.name, confirmed, title);
      const create = panels(page).create;
      await create.getByLabel("Identifier", {exact: true}).fill(identifier(info, "fail"));
      await create.getByLabel("Text", {exact: true}).fill("Unconfirmed replacement");
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
      await expect(create.getByRole("definition").nth(0)).toHaveText(confirmed);
      expect(await create.getByRole("definition").nth(1).textContent()).toBe(title);
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
      await load(page, app.name);
      const firstReady = deferred();
      const releaseFirst = deferred();
      const firstFinished = deferred();
      let firstStatus: number | undefined;
      await page.route(`**/api/${app.name}`, async route => {
        const data = route.request().postDataJSON();
        if (data?.action !== "fetch" || data?.input?.fields?.selected_id !== ids[1]) {
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
        const first = panels(page).listing.getByRole("row").filter({hasText: ids[1]});
        await first.getByRole("button", {name: /^Select /}).click();
        await firstReady.promise;
        expect(firstStatus).toBe(200);
        await turnPage(page, app.name, "Next", 2, 2);
        await select(page, app.name, ids[0], titles[0]);
        releaseFirst.resolve();
        await firstFinished.promise;
        await frames(page);
        await expect(panels(page).detail.getByRole("cell", {name: ids[0], exact: true}))
          .toBeVisible();
        await expect(panels(page).detail.getByRole("cell", {name: ids[1], exact: true}))
          .toHaveCount(0);
        await expect(panels(page).detail.getByRole("status"))
          .toHaveText("Selection loaded · Confirmation 1");
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
        const controls = page.getByRole("main").locator("input,textarea,select,button");
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
