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
  await page.getByLabel("Тип диалога").selectOption("knowledge");
  await expect(page.getByRole("link", { name: title })).toHaveCount(0);
  await page.getByLabel("Тип диалога").selectOption("declaration");
  await page.getByLabel("Поиск по названию, автору или ID").fill(id);
  await page.getByRole("button", { name: "Найти" }).click();
  await page.getByRole("link", { name: title, exact: true }).click();
  await expect(page.getByRole("heading", { name: "История диалога" })).toBeVisible();
  await page.locator("summary").filter({ hasText: "Шагов агента" }).click();
  await expect(page.locator(".log-steps")).toContainText("Чтение документа");
  await expect(page.locator(".log-steps")).toContainText("Извлечение фактов из комплекта");
  await page.locator("summary").filter({ hasText: "Вопросы после анализа" }).click();
  await expect(page.getByText(/Графа 1 ·/).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
