import { readFile } from "node:fs/promises";
import { test, expect } from "@playwright/test";

test("login, upload, analyze, fill missing details, download XML and reopen on mobile", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (r) => {
    if (r.status() >= 500) errors.push(r.status() + " " + r.url());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.goto("/workspace/");
  await page.getByLabel("Email", { exact: true }).fill("qa@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(process.env.FORMA_QA_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("heading", { name: "С какой поставкой работаем?" })).toBeVisible();
  const provider = await page.request.put("/api/admin/providers/deepseek", {
    data: { base_url: "https://api.deepseek.com/v1", api_key: "synthetic-browser-test" },
  });
  expect(provider.ok()).toBeTruthy();
  await page.getByRole("button", { name: "Новая декларация" }).click();
  const dialog = page.getByRole("dialog");
  const title = dialog.getByLabel("Название диалога");
  await expect(title).toBeFocused();
  await title.fill("Проверка поставки");
  await dialog.getByRole("button", { name: "Создать декларацию" }).click();
  await expect(page.getByRole("heading", { name: "Проверка поставки" })).toBeVisible();
  const shipmentURL = page.url();
  await page.locator('input[type="file"]').setInputFiles({
    name: "invoice.txt", mimeType: "text/plain", buffer: Buffer.from("Pump P1 100 kg 50 EUR. Declarant: QA Company"),
  });
  await page.getByRole("button", { name: "Отправить документы на анализ" }).click();
  const gaps = page.getByRole("button", { name: /^Незаполненные графы:/ });
  await gaps.click();
  await dialog.getByRole("button", { name: /Графа 14 / }).click();
  await dialog.getByRole("textbox", { name: "Город", exact: true }).fill("Казань");
  await dialog.locator("details > summary").first().click();
  const source = dialog.getByRole("button", { name: /invoice\.txt/ }).first();
  await source.click();
  const preview = page.getByRole("dialog", { name: "invoice.txt" });
  await expect(preview).toContainText("Pump P1");
  expect(await page.evaluate(() => window.dispatchEvent(new Event("beforeunload", { cancelable: true })))).toBe(false);
  await preview.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(source).toBeFocused();
  await expect(dialog.getByRole("textbox", { name: "Город", exact: true })).toHaveValue("Казань");
  await dialog.getByRole("button", { name: "Сохранить реквизиты" }).click();
  await expect(dialog.getByRole("heading", { name: /Незаполненные графы/ })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "XML-проект", exact: true }).click();
  const downloading = page.waitForEvent("download");
  await dialog.getByRole("link", { name: "Скачать XML-проект" }).click();
  const file = await downloading;
  const xml = await readFile(await file.path());
  expect(xml.toString("ascii")).toContain("<AltaGTD");
  expect(xml.toString("ascii")).toContain("G_35_1>100<");
  await page.goto("/admin/#/team");
  await expect(page.getByRole("heading", { name: /Сотрудники/ })).toBeVisible();
  await expect(page.getByRole("row").filter({ hasText: "qa@example.test" })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(shipmentURL);
  await gaps.click();
  await dialog.getByRole("button", { name: /Графа 14 / }).click();
  await expect(dialog.getByRole("textbox", { name: "Город", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
