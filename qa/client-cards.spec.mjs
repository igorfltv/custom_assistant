import { expect, test } from "@playwright/test";

test("save a reviewed party and reuse it in another role before uploading files", async ({
  page,
}) => {
  await page.goto("/workspace/");
  await page.getByLabel("Email", { exact: true }).fill("qa@example.test");
  await page
    .getByLabel("Пароль", { exact: true })
    .fill(process.env.FORMA_QA_PASSWORD);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Поставки", exact: true }),
  ).toBeVisible();
  expect(
    (
      await page.request.put("/api/admin/providers/deepseek", {
        data: {
          base_url: "https://api.deepseek.com/v1",
          api_key: "synthetic-browser-test",
        },
      })
    ).ok(),
  ).toBeTruthy();
  const { id } = await (
    await page.request.post("/api/declarations", {
      data: { title: "Карточка из инвойса" },
    })
  ).json();
  const path = "/api/declarations/" + id;
  expect(
    (
      await page.request.post(path + "/documents", {
        multipart: {
          file: {
            name: "source-client.txt",
            mimeType: "text/plain",
            buffer: Buffer.from("Declarant: QA Company. Pump P1 100 kg."),
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  expect((await page.request.post(path + "/analyze")).ok()).toBeTruthy();
  await page.goto("/workspace/#/declaration/" + id);
  await page
    .getByRole("button", { name: "Сохранить клиента", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Название карточки")).toHaveValue(
    "QA Company",
  );
  await expect(dialog.getByText(/source-client.txt/)).toBeVisible();
  await expect(dialog.getByLabel(/Наименование/)).toBeChecked();
  await dialog.getByRole("button", { name: "Сохранить карточку" }).click();
  await expect(dialog.getByRole("status")).toHaveText(/QA Company.*Версия 1/);
  await dialog.getByRole("button", { name: "Готово" }).click();
  await page.goto("/workspace/#/");
  await page.setViewportSize({ width: 320, height: 740 });
  await page.getByRole("button", { name: "Создать поставку" }).click();
  await dialog.getByLabel("Название поставки").fill("Повторное обращение");
  await dialog.getByRole("button", { name: "Выбрать клиента" }).click();
  await dialog.getByLabel("Поиск по названию или ИНН").fill("qa comp");
  await dialog
    .getByLabel("Клиент из справочника")
    .selectOption({ label: "QA Company" });
  await dialog.getByRole("button", { name: "Создать декларацию" }).click();
  await expect(dialog.getByLabel("Роль клиента в поставке")).toBeFocused();
  await dialog.getByLabel("Роль клиента в поставке").selectOption("consignee");
  await dialog.getByRole("button", { name: "Создать декларацию" }).click();
  await expect(
    page.getByRole("heading", { name: "Повторное обращение" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Параметры поставки" }).click();
  await dialog.getByText(/Карточка клиента · QA Company/).click();
  await expect(dialog.getByText("Получатель · графа 8")).toBeVisible();
  await expect(dialog.getByText(/source-client.txt/)).toBeVisible();
  const result = await (
    await page.request.get("/api/declarations/" + page.url().split("/").pop())
  ).json();
  expect(result.fields.map((f) => f.graph)).toEqual(["8"]);
  expect(result.documents).toEqual([]);
  expect(result.runs).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});
