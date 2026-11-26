import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  const response = await page.request.post("/api/auth/login", {
    data: { email: "qa@example.test", password: process.env.FORMA_QA_PASSWORD },
  });
  expect(response.ok()).toBe(true);
});

test("return to a filtered shipment beyond the first page on desktop and mobile", async ({
  page,
}) => {
  const client = "Клиент для проверки реестра";
  for (let i = 0; i < 21; i++) {
    const response = await page.request.post("/api/declarations", {
      data: { title: "Партия " + i, client },
    });
    expect(response.ok()).toBe(true);
  }
  await page.goto("/workspace/");
  const board = page.getByRole("table", { name: "Список поставок" });
  const search = page.getByRole("searchbox", { name: "Найти поставку" });
  await search.fill(client);
  await page.getByRole("button", { name: "Подготовка 21" }).click();
  await expect(board.getByRole("link")).toHaveCount(20);
  await page.getByRole("button", { name: /Показать ещё/ }).click();
  const last = board.getByRole("link").last();
  const title = await last.textContent();
  // Follow the stretched link by clicking the action column away from its text.
  const actionCell = board.getByRole("row").last().getByRole("cell").last();
  await actionCell.scrollIntoViewIfNeeded();
  const bounds = await actionCell.boundingBox();
  await page.mouse.click(bounds.x + 8, bounds.y + 8);
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(last).toBeFocused();
  await expect(search).toHaveValue(client);
  await expect(board.getByRole("link")).toHaveCount(21);
  await page.setViewportSize({ width: 320, height: 740 });
  const queue = page.getByRole("combobox", { name: "Этап подготовки" });
  await expect(queue).toHaveValue("2");
  await last.press("Enter");
  await page.getByRole("link", { name: "Все поставки", exact: true }).click();
  await expect(last).toBeFocused();
  await queue.selectOption({ label: "С ошибкой (0)" });
  await expect(
    page.getByRole("heading", { name: "Поставки не найдены" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Сбросить условия" }).click();
  await expect(search).toBeFocused();
  await expect(search).toHaveValue("");
  await expect(queue).toHaveValue("0");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("upload without configured models and analyze the saved files when configuration is available", async ({
  page,
}) => {
  expect(
    (
      await page.request.put("/api/admin/providers/deepseek", {
        data: {
          base_url: "https://api.deepseek.com/v1",
          api_key: "synthetic-browser-test",
        },
      })
    ).ok(),
  ).toBe(true);
  const { id } = await (
    await page.request.post("/api/declarations", {
      data: { title: "Комплект до настройки моделей" },
    })
  ).json();
  await page.route("**/api/profile", async (route) => {
    const response = await route.fetch();
    const profile = await response.json();
    await route.fulfill({ response, json: { ...profile, connections: {} } });
  });
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto("/workspace/#/declaration/" + id);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Выбрать файлы" }).click();
  await (
    await chooser
  ).setFiles({
    name: "invoice.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Pump P1 100 kg QA Company"),
  });
  await expect(page.getByText("Файлов к загрузке: 1")).toBeVisible();
  await page
    .getByRole("button", { name: "Загрузить файлы", exact: true })
    .click();
  const document = page.getByRole("button", { name: /invoice\.txt/ }).first();
  await expect(document).toBeVisible();
  const draft = await (
    await page.request.get("/api/declarations/" + id)
  ).json();
  expect(draft.documents).toHaveLength(1);
  expect(draft.runs).toHaveLength(0);
  await page.unroute("**/api/profile");
  await page.reload();
  await page.getByRole("button", { name: "Черновик", exact: true }).click();
  await page.getByRole("button", { name: "К документам" }).click();
  await expect(
    page.getByRole("button", { name: "Добавить ещё файлы" }),
  ).toBeFocused();
  await page
    .getByRole("button", { name: "Начать анализ", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Замечания по графам" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Черновик", exact: true }).click();
  await page.getByRole("button", { name: "XML-проект", exact: true }).click();
  await expect(
    page.getByRole("dialog").getByRole("link", { name: "Скачать XML-проект" }),
  ).toBeInViewport();
});
