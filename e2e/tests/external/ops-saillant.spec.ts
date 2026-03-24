import { test, expect } from "@playwright/test";

/**
 * Smoke tests externes sur ops.saillant.cc.
 * Ces tests valident uniquement la disponibilite, la navigation initiale et
 * l'absence de crash UI evident. Ils restent volontairement souples.
 */

test.describe("ops.saillant.cc smoke", () => {
  test("la page d'accueil est reachable", async ({ page, baseURL }) => {
    const response = await page.goto(baseURL || "https://ops.saillant.cc", { waitUntil: "domcontentloaded" });
    expect(response).not.toBeNull();
    expect(response!.status()).toBeLessThan(500);
    await expect(page.locator("body")).toBeVisible();
  });

  test("le titre de page est defini", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const title = await page.title();
    expect(title.trim().length).toBeGreaterThan(0);
  });

  test("la page ne contient pas d'erreur serveur brute", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const content = await page.content();
    expect(content).not.toContain("502 Bad Gateway");
    expect(content).not.toContain("503 Service Unavailable");
  });

  test("la page ne doit pas afficher l'ecran Application Error", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Application Error", { exact: false })).toHaveCount(0);
  });
});
