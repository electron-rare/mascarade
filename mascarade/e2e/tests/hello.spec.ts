import { test, expect } from '@playwright/test';

test('hello world test', async ({ page }) => {
    await page.goto('http://localhost:3000'); // Remplacez par l'URL de votre application
    const title = await page.title();
    expect(title).toBe('Titre attendu'); // Remplacez par le titre attendu de votre page
});