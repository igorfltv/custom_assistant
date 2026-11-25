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
  await expect(page.getByRole("heading", { name: "Поставки", exact: true })).toBeVisible();
  const provider = await page.request.put("/api/admin/providers/deepseek", {
    data: { base_url: "https://api.deepseek.com/v1", api_key: "synthetic-browser-test" },
  });
  expect(provider.ok()).toBeTruthy();
  await page.getByRole("button", { name: "Новая декларация" }).click();
  const dialog = page.getByRole("dialog");
  const title = dialog.getByLabel("Название поставки");
  await expect(title).toBeFocused();
  await title.fill("Проверка поставки");
  await dialog.getByRole("button", { name: "Создать декларацию" }).click();
  await expect(page.getByRole("heading", { name: "Проверка поставки" })).toBeVisible();
  const shipmentURL = page.url();
  await page.locator('input[type="file"]').setInputFiles({
    name: "invoice.txt", mimeType: "text/plain", buffer: Buffer.from("Pump P1 100 kg 50 EUR. Declarant: QA Company"),
  });
  await page.getByRole("button", { name: "Отправить документы на анализ" }).click();
  const review = page.getByRole("region", {name: "Замечания по графам"});
  const graph14 = review.locator(".graph-review-card").filter({has: page.locator("summary strong", {hasText: /^Графа 14$/})});
  const openGraph = async () => {
    await review.getByRole("searchbox").fill("графа 14");
    await graph14.locator("summary").click();
    await expect(graph14).toContainText("Заполнена частично");
    await expect(graph14).toContainText("QA Company");
    await graph14.getByRole("button", {name: "Дополнить графу"}).click();
  };
  await openGraph();
  await dialog.getByRole("textbox", { name: "Город", exact: true }).fill("Казань");
  await dialog.getByText("Запомнить правило для следующих деклараций").click();
  await dialog.getByLabel("Правило для моих деклараций").fill("Для графы 14 сверяй город с карточкой декларанта.");
  await dialog.locator(".missing-guidance details > summary").first().click();
  const source = dialog.getByRole("button", { name: /invoice\.txt/ }).first();
  await source.click();
  const preview = page.getByRole("dialog", { name: "invoice.txt" });
  await expect(preview).toContainText("Pump P1");
  expect(await page.evaluate(() => window.dispatchEvent(new Event("beforeunload", { cancelable: true })))).toBe(false);
  await preview.getByRole("button", { name: "Закрыть", exact: true }).click();
  await expect(source).toBeFocused();
  await expect(dialog.getByRole("textbox", { name: "Город", exact: true })).toHaveValue("Казань");
  await dialog.getByRole("button", { name: "Сохранить реквизиты" }).click();
  await expect(page.getByRole("dialog", { name: /Графа 14/ })).toHaveCount(0);
  await expect(review).toBeVisible();
  const memory = await (await page.request.get("/api/me/memory")).json();
  const saved = memory.items.find((note) => note.text === "Для графы 14 сверяй город с карточкой декларанта.");
  expect(saved?.graph).toBe("14");
  await page.request.delete("/api/me/memory/" + saved.id);
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
  await openGraph();
  await expect(dialog.getByRole("textbox", { name: "Город", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});
