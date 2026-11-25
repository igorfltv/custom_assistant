import { test, expect } from "@playwright/test";

test("remember a chat correction, edit it across dialogs and forget it", async ({ page }) => {
  await page.request.post("/api/auth/login", {
    data: { email: "qa@example.test", password: process.env.FORMA_QA_PASSWORD },
  });
  await page.goto("/workspace/#/knowledge");
  const instruction = "Всегда сверяй артикул с маркировкой на упаковке.";
  await page.getByLabel("Ваш вопрос по базе знаний").fill("Запомни: " + instruction);
  await page.getByRole("button", {name: "Отправить вопрос"}).click();
  await expect(page.getByText("Сохранено в моей памяти: «" + instruction + "».")).toBeVisible();
  await page.getByRole("button", {name: "Новый диалог"}).click();
  await page.getByText("Моя память", {exact: true}).click();
  const panel = page.locator(".personal-memory");
  await expect(panel).toContainText(instruction);
  await panel.getByRole("button", {name: "Изменить"}).click();
  await panel.getByLabel("Текст правила").fill("Сверяй артикул с маркировкой в спецификации.");
  await panel.getByRole("button", {name: "Сохранить"}).click();
  await expect(panel.getByText("Сверяй артикул с маркировкой в спецификации.")).toBeVisible();
  const admin = await page.context().newPage();
  await admin.goto("/admin/");
  await admin.getByRole("link", { name: "Память пользователей" }).click();
  const rule = admin.getByRole("row", { name: /Сверяй артикул с маркировкой в спецификации/ });
  await expect(rule).toContainText("qa@example.test");
  await expect(rule).toContainText("Все клиенты");
  const search = admin.getByRole("searchbox", { name: "Поиск по памяти" });
  await search.fill("отсутствующий артикул");
  await search.press("Enter");
  await expect(admin.getByRole("status")).toHaveText("По вашему запросу правил не найдено.");
  await admin.getByRole("button", { name: "Сбросить поиск" }).click();
  await expect(rule).toBeVisible();
  await admin.setViewportSize({ width: 320, height: 800 });
  await search.fill("СПЕЦИФИКАЦИИ");
  await admin.getByRole("button", { name: "Найти" }).click();
  await expect(admin.getByText("Найдено правил · 1")).toBeVisible();
  await expect(rule).toBeVisible();
  expect(await admin.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.reload();
  await page.getByText("Моя память", {exact: true}).click();
  await panel.getByRole("button", {name: "Забыть"}).click();
  await expect(panel).toContainText("Пока нет правил");
  await admin.getByRole("button", { name: "Обновить" }).click();
  await expect(admin.getByText("По вашему запросу правил не найдено.")).toBeVisible();
  await admin.close();
});
