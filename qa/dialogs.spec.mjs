import { test, expect } from "@playwright/test";

test("administrator opens and inspects a declaration from the dialogue journal", async ({ page }) => {
  await page.goto("/admin/");
  await page.getByLabel("Email", { exact: true }).fill("qa@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(process.env.FORMA_QA_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("link", { name: "Журнал диалогов" })).toBeVisible();
  expect((await page.request.put("/api/admin/providers/deepseek", {
    data: { base_url: "https://api.deepseek.com/v1", api_key: "synthetic-browser-test" },
  })).ok()).toBeTruthy();
  const title = "Проверка журнала поставки";
  const { id } = await (await page.request.post("/api/declarations", { data: { title } })).json();
  const shipment = "/api/declarations/" + id;
  expect((await page.request.post(shipment + "/documents", { multipart: {
    file: { name: "invoice.txt", mimeType: "text/plain", buffer: Buffer.from("Pump P1 100 kg 50 EUR. Declarant: QA Company") },
  } })).ok()).toBeTruthy();
  expect((await page.request.post(shipment + "/analyze")).ok()).toBeTruthy();
  await page.getByRole("link", { name: "Журнал диалогов" }).click();
  const search = page.getByRole("searchbox", { name: "Поиск по журналу" });
  const kind = page.getByLabel("Тип диалога");
  const submit = page.getByRole("button", { name: "Найти" });
  await expect(page.getByRole("link", { name: title, exact: true })).toBeVisible();
  const [inputBox, kindBox, buttonBox] = await Promise.all([search, kind, submit].map(control => control.boundingBox()));
  expect(Math.abs(inputBox.y - kindBox.y)).toBeLessThan(2);
  expect(Math.abs(inputBox.y - buttonBox.y)).toBeLessThan(2);
  expect(inputBox.width).toBeGreaterThan(kindBox.width);
  expect(inputBox.height).toBeLessThan(60);
  await kind.selectOption("knowledge");
  await expect(page.getByRole("link", { name: title })).toHaveCount(0);
  await kind.selectOption("declaration");
  await search.fill("missing-" + id);
  await search.press("Enter");
  await expect(page.getByText("Диалоги не найдены.")).toBeVisible();
  await page.getByRole("button", { name: "Сбросить фильтры" }).click();
  await expect(search).toHaveValue("");
  await expect(kind).toHaveValue("");
  await expect(page.getByRole("link", { name: title, exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  const [mobileInput, mobileKind, mobileSubmit] = await Promise.all([search, kind, submit].map(control => control.boundingBox()));
  expect(mobileInput.y + mobileInput.height).toBeLessThan(mobileKind.y);
  expect(Math.abs(mobileKind.y - mobileSubmit.y)).toBeLessThan(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await kind.selectOption("declaration");
  await search.fill(id);
  await submit.click();
  await page.getByRole("link", { name: title, exact: true }).click();
  await expect(page.getByRole("heading", { name: "История диалога" })).toBeVisible();
  await page.locator("summary").filter({ hasText: "Шагов агента" }).click();
  await expect(page.locator(".log-steps")).toContainText("Чтение документа");
  await expect(page.locator(".log-steps")).toContainText("Извлечение фактов из комплекта");
  await page.locator("summary").filter({ hasText: "Вопросы после анализа" }).click();
  await expect(page.getByText(/Графа 1 ·/).first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("link", { name: "← Журнал диалогов" }).click();
  await expect(search).toHaveValue(id);
  await expect(kind).toHaveValue("declaration");
  await expect(page.getByRole("link", { name: title, exact: true })).toBeVisible();
});
