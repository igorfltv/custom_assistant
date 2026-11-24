import { expect, test } from "@playwright/test";

test("administrator cancels and then confirms removal of a disabled employee", async ({ page }) => {
  await page.goto("/admin/#/team");
  await page.getByLabel("Email", { exact: true }).fill("qa@example.test");
  await page.getByLabel("Пароль", { exact: true }).fill(process.env.FORMA_QA_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  const team = page.getByRole("table").first();
  await expect(team.getByRole("row").filter({ hasText: "qa@example.test" })).toContainText("Это вы");
  const email = "remove-employee@example.test";
  const invite = await page.request.post("/api/admin/invites", { data: { email } });
  expect(invite.status()).toBe(201);
  const token = (await invite.json()).url.split("/").pop();
  expect((await page.request.post("/api/auth/invite", { data: {
    name: "Сотрудник для проверки", token, password: "Synthetic-password-2026!",
  } })).ok()).toBeTruthy();
  await page.getByRole("button", { name: "Обновить" }).click();
  const employee = team.getByRole("row").filter({ hasText: email });
  await employee.getByRole("button", { name: "Отключить" }).click();
  await expect(employee).toContainText("Отключён");
  const remove = employee.getByRole("button", { name: "Удалить" });
  const modal = page.getByRole("dialog", { name: "Удалить сотрудника?" });
  await remove.click();
  await expect(modal).toContainText(email);
  await expect(modal).toContainText("Сотрудник для проверки");
  await expect(modal.getByRole("button", { name: "Отмена" })).toBeFocused();
  await modal.getByRole("button", { name: "Отмена" }).click();
  await expect(employee).toBeVisible();
  await remove.click();
  await modal.getByRole("button", { name: "Удалить сотрудника", exact: true }).click();
  await expect(employee).toHaveCount(0);
  await page.reload();
  await expect(team.getByRole("row").filter({ hasText: "qa@example.test" })).toBeVisible();
  await expect(employee).toHaveCount(0);
});
