import { test, expect } from "@playwright/test";

test("admin replaces an opened invite and sees which link registered the employee", async ({ page, browser }) => {
  const email = "invited@example.test";
  const password = "Synthetic-invite-2026!";
  await page.goto("/admin/#/team");
  await page.getByLabel("Email", { exact: true }).fill("qa@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(process.env.FORMA_QA_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await page.getByRole("button", { name: "Пригласить сотрудника" }).click();
  const modal = page.getByRole("dialog");
  await modal.getByLabel("Email сотрудника").fill(email);
  await modal.getByRole("button", { name: "Создать приглашение" }).click();
  await expect(modal).toContainText("24 часа");
  const original = await modal.getByLabel("Ссылка-приглашение").inputValue();
  await modal.getByRole("button", { name: "Закрыть" }).click();

  const history = page.getByRole("table", { name: "Приглашения" });
  const row = history.getByRole("row").filter({ hasText: email });
  await expect(row).toContainText("Переходов пока нет");
  const guest = await browser.newPage();
  try {
    await guest.goto(original);
    const loginEmail = guest.getByRole("textbox", { name: "Email для входа", exact: true });
    await expect(loginEmail).toBeVisible();
    await expect(loginEmail).toHaveValue(email);
    await expect(loginEmail).not.toBeEditable();
    await guest.getByLabel("Ваше имя").fill("Мария");
    await guest.getByLabel("Придумайте пароль").fill(password);
    await page.getByRole("button", { name: "Обновить" }).click();
    await expect(row.getByRole("cell").nth(2).locator("time")).toBeVisible();
    await expect(row.getByRole("cell").nth(3)).toHaveText("Нет");
    await row.getByRole("button", { name: "Перевыпустить" }).click();
    await modal.getByRole("button", { name: "Создать новую ссылку" }).click();
    const replacement = await modal.getByLabel("Ссылка-приглашение").inputValue();
    expect(replacement).not.toBe(original);
    await modal.getByRole("button", { name: "Закрыть" }).click();

    await guest.getByRole("button", { name: "Создать учётную запись" }).click();
    await expect(guest.getByRole("alert")).toBeVisible();
    await guest.reload();
    await expect(guest.getByText(/Приглашение отозвано/)).toBeVisible();
    await guest.goto(replacement);
    await expect(loginEmail).toHaveValue(email);
    await guest.getByLabel("Ваше имя").fill("Мария");
    await guest.getByLabel("Придумайте пароль").fill(password);
    await guest.getByRole("button", { name: "Создать учётную запись" }).click();
    await expect(guest.getByRole("status")).toContainText(email);
    await guest.getByRole("link", { name: /Войти в кабинет/ }).click();
    await guest.getByLabel("Email", { exact: true }).fill(email);
    await guest.getByLabel("Пароль", { exact: true }).fill(password);
    await guest.getByRole("button", { name: "Войти", exact: true }).click();
    await expect(guest.getByRole("heading", { name: "Поставки", exact: true })).toBeVisible();
  } finally {
    await guest.close();
  }

  await page.getByRole("button", { name: "Обновить" }).click();
  await expect(row).toHaveCount(2);
  await expect(row.filter({ hasText: "Отозвана" }).getByRole("cell").nth(3)).toHaveText("Нет");
  await expect(row.filter({ hasText: "Использована" })).toContainText("Зарегистрирован");
  await expect(history.getByRole("button", { name: "Перевыпустить" })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
