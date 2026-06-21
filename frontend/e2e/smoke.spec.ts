import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// Smoke e2e: the login page renders and is accessible. Runs against a local
// `next start` build (see playwright.config.ts). NOT part of the CI node gate.
test("login page renders and has no critical a11y violations", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Trustee Platform" }),
  ).toBeVisible();
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();

  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious).toEqual([]);
});

test("unauthenticated visit to the dashboard redirects to login", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});
