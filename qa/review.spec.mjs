import { test, expect } from "@playwright/test";

test("review a documented choice, inspect its source, save and resume from the queue", async ({
  page,
}, testInfo) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
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
  await page
    .getByRole("button", { name: "Создать поставку", exact: true })
    .click();
  await page.getByLabel("Название поставки").fill("Проверка валюты счёта");
  await page.getByRole("button", { name: "Создать декларацию" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "invoice-currency.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(
      "Pump P1 100 kg 50 EUR. Declarant: QA Company. Currency options: EUR / USD",
    ),
  });
  await page
    .getByRole("button", { name: "Отправить документы на анализ" })
    .click();
  const card = page.getByRole("region", { name: "Текущее замечание" });
  const choose = card.getByRole("button", { name: "Подставить «USD»" });
  await expect(choose).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("review-desktop.png") });
  await card
    .getByRole("button", { name: "invoice-currency.txt" })
    .first()
    .click();
  const source = page.getByRole("dialog", { name: "invoice-currency.txt" });
  await expect(source.locator("mark").first()).toHaveText(
    "Currency options: EUR / USD",
  );
  await source.getByRole("button", { name: "Закрыть" }).click();
  await choose.click();
  await expect(card.getByRole("textbox")).toHaveValue("USD");
  const id = page.url().split("/").pop();
  const detail = () =>
    page.request.get("/api/declarations/" + id).then((r) => r.json());
  expect((await detail()).answers.length).toBe(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Показать на бланке" }).click();
  await expect(page.locator('.dt-cell[data-graph="22"]')).toBeFocused();
  await page
    .getByRole("navigation", { name: "Рабочее пространство", exact: true })
    .getByRole("button", { name: "Проверка" })
    .click();
  await expect(card.getByRole("textbox")).toHaveValue("USD");
  await page.screenshot({ path: testInfo.outputPath("review-mobile.png") });
  await card.getByRole("button", { name: "Сохранить значение" }).click();
  await page.getByRole("button", { name: "Ответы · 1" }).click();
  await expect(
    page.getByText("Выбрано по документу", { exact: true }),
  ).toBeVisible();
  const saved = await detail();
  expect(saved.answers[0].source.filename).toBe("invoice-currency.txt");
  expect(
    saved.fields
      .find((f) => f.graph === "22")
      .parts.find((p) => p.key === "currency").value,
  ).toBe("USD");
  await page.goto("/workspace/#/");
  await page
    .getByRole("searchbox", { name: "Найти поставку" })
    .fill("Проверка валюты");
  const list = page.locator(".shipment-list");
  await expect(list.getByRole("link")).toHaveCount(1);
  await list.getByRole("link").click();
  await expect(page.getByRole("button", { name: "Ответы · 1" })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});

test("an XML issue opens its own register entry and repairs only that entry", async ({
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
      data: { title: "Реестр документов" },
    })
  ).json();
  const api = "/api/declarations/" + id;
  expect(
    (
      await page.request.post(api + "/documents", {
        multipart: {
          file: {
            name: "register.txt",
            mimeType: "text/plain",
            buffer: Buffer.from(
              "Pump P1 100 kg QA Company. Valve P2. REGISTER-QA Certificate A AA-1. Certificate B BB-2.",
            ),
          },
        },
      })
    ).ok(),
  ).toBeTruthy();
  expect((await page.request.post(api + "/analyze")).ok()).toBeTruthy();
  await page.goto("/workspace/#/declaration/" + id);
  await page.getByRole("button", { name: "XML-проект", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByRole("listitem")
    .filter({ hasText: "Certificate B" })
    .first()
    .getByRole("button")
    .click();
  await expect(
    dialog.getByRole("combobox", { name: "Документ", exact: true }),
  ).toHaveValue("1");
  await expect(dialog.getByLabel("Номер документа")).toHaveValue("BB-2");
  await dialog.getByLabel("Код вида документа").fill("12345");
  await dialog.getByRole("button", { name: /Открыть источник/ }).click();
  await page
    .getByRole("dialog", { name: "register.txt" })
    .getByRole("button", { name: "Закрыть" })
    .click();
  await expect(dialog.getByLabel("Включить все совпадения")).not.toBeChecked();
  await dialog.getByLabel("Включить все совпадения").check();
  await dialog
    .getByRole("button", { name: "Сохранить для товаров · 2" })
    .click();
  await expect(dialog).toHaveCount(0);
  const saved = await (await page.request.get(api)).json();
  const fields = saved.fields.filter((f) => f.graph === "44");
  expect(fields).toHaveLength(2);
  for (const field of fields)
    expect(field.documents.map((d) => d.type_code)).toEqual([null, "12345"]);
  expect(saved.export_issues.filter((i) => i.graph === "44")).toHaveLength(2);
  await page
    .getByRole("button", { name: "Общие для товаров · 1", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByRole("button", { name: /Certificate A/ }),
  ).toHaveCount(1);
});

test("the operator can trace a dated legal finding to its archived passage", async ({
  page,
}, testInfo) => {
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
  await page
    .getByRole("button", { name: "Создать поставку", exact: true })
    .click();
  await page.getByLabel("Название поставки").fill("Проверка редакции");
  await page.getByRole("button", { name: "Создать декларацию" }).click();
  await page
    .getByRole("button", { name: "Параметры поставки", exact: true })
    .click();
  const settings = page.getByRole("dialog", { name: "Параметры поставки" });
  await settings.getByLabel("Дата для проверки редакций").fill("2026-11-15");
  await settings.getByRole("button", { name: "Сохранить параметры" }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: "LEGAL-QA.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("LEGAL-QA. Pump P1 100 kg. Declarant: QA Company."),
  });
  await page
    .getByRole("button", { name: "Отправить документы на анализ" })
    .click();
  await expect(
    page.getByRole("region", { name: "Текущее замечание" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Контекст поставки", exact: true })
    .first()
    .click();
  const point = page
    .locator(".context-point")
    .filter({ hasText: "Сверьте основание массы брутто." });
  await expect(
    point.getByText("Применимость редакции на 15.11.2026 требует проверки"),
  ).toBeVisible();
  await point
    .getByRole("button", { name: "Открыть сохранённую редакцию" })
    .click();
  await expect(point.locator("mark")).toHaveText(
    "Сверьте массу с упаковочным листом.",
  );
  await expect(point.getByRole("link", { name: "Публикация" })).toHaveAttribute(
    "href",
    /ST106/,
  );
  await point.screenshot({ path: testInfo.outputPath("legal-citation.png") });
  await point.getByText("Полный текст редакции").click();
  await expect(point.locator("pre")).toContainText("Конец примера.");
  await point
    .getByRole("button", { name: "Графа 35 · товар №1 на бланке" })
    .click();
  await expect(
    page.locator('.dt-cell[data-graph="35"][data-item="1"]'),
  ).toBeFocused();
});
