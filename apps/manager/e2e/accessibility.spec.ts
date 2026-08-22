import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const criticalJourneys = [
  { name: "torre de controlo", path: "/" },
  { name: "receção da oficina", path: "/oficina" },
  { name: "ordens de serviço", path: "/oficina/ordens-servico" },
  { name: "viaturas", path: "/viaturas" },
  { name: "motoristas", path: "/motoristas" },
];

for (const journey of criticalJourneys) {
  test(`${journey.name} não tem violações axe A/AA detectáveis`, async ({ page }) => {
    await page.goto(journey.path);
    await expect(page.locator("#main-content")).toBeVisible();

    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();

    expect(
      result.violations,
      result.violations
        .map(
          (violation) =>
            `${violation.id} (${violation.impact}): ${violation.nodes
              .map((node) => node.target.join(" "))
              .join(", ")}`,
        )
        .join("\n"),
    ).toEqual([]);
  });
}

test("skip link transfere o foco para o conteúdo principal", async ({ page }) => {
  await page.goto("/oficina");
  const skipLink = page.getByRole("link", { name: "Saltar para o conteúdo principal" });
  await skipLink.focus();
  await expect(skipLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
});

