import { expect, test } from "@playwright/test";

test("feedback on a declaration survives a lost response and reaches the journal and export", async ({ page }) => {
  await page.request.post("/api/auth/login", {
    data: { email: "qa@example.test", password: process.env.FORMA_QA_PASSWORD },
  });
  const { id } = await (await page.request.post("/api/declarations", {
    data: { title: "Обратная связь по поставке оборудования" },
  })).json();
  const shipment = "/api/declarations/" + id;
  expect((await page.request.put("/api/admin/providers/deepseek", {
    data: { base_url: "https://api.deepseek.com/v1", api_key: "synthetic-browser-test" },
  })).ok()).toBe(true);
  expect((await page.request.post(shipment + "/documents", { multipart: {
    file: { name: "invoice.txt", mimeType: "text/plain", buffer: Buffer.from("Pump P1 100 kg 50 EUR. Declarant: QA Company") },
  } })).ok()).toBe(true);
  const run = await page.request.post(shipment + "/analyze");
  expect(run.ok()).toBe(true);
  const { run_id } = await run.json();
  await page.goto("/workspace/#/declaration/" + id);
  const open = page.getByRole("button", { name: "Обратная связь", exact: true });
  await expect(open).toBeVisible();
  await page.setViewportSize({ width: 320, height: 740 });
  await open.click();
  const modal = page.getByRole("dialog", { name: "Обратная связь", exact: true });
  const input = modal.getByRole("textbox", { name: "Что пошло не так при разборе?" });
  const submit = modal.getByRole("button", { name: "Отправить отзыв" });
  await expect(input).toBeFocused();
  await expect(submit).toBeDisabled();
  const comment = "Агент объединил два товара.\nВ инвойсе насос и клапан указаны отдельно.";
  await input.fill(comment);
  await page.route("**/declarations/" + id + "/feedback", async (route) => {
    const response = await route.fetch();
    expect(response.ok()).toBe(true);
    await route.abort();
  }, { times: 1 });
  await submit.click();
  await expect(modal.getByRole("alert")).toBeVisible();
  await expect(input).toHaveValue(comment);
  await submit.click();
  await expect(modal.getByRole("status")).toHaveText("Отзыв сохранён.");
  await modal.getByRole("button", { name: "Готово" }).click();
  await expect(open).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  await page.goto("/admin/#/dialogs/declaration/" + id);
  const entry = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Обратная связь по разбору" }) });
  await expect(entry).toHaveCount(1);
  await expect(entry).toContainText("qa@example.test");
  await expect(entry).toContainText(run_id);
  await expect(entry.locator("p")).toHaveText(comment);
  await page.goto("/admin/#/models");
  await page.locator("summary").filter({ hasText: "Исправления и обучение" }).click();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Скачать отзывы в JSONL" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("declaration-feedback.jsonl");
  const chunks = [];
  for await (const chunk of await file.createReadStream()) chunks.push(chunk);
  const rows = Buffer.concat(chunks).toString().trim().split("\n").map(JSON.parse);
  expect(rows.filter((row) => row.declaration_id === id).map((row) => row.text)).toEqual([comment]);
});
