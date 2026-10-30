import { expect, type Page, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomMemoryTitle, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

// These tests read the items the AI extracted from a story, so the backend must run
// with AI_BACKEND=fake: it extracts one fact per sentence, without waiting for Ollama.

test.describe("Confirming extracted memories", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string
  let memoryTitle: string
  const password = randomPassword()

  const extractedItems = (page: Page) =>
    page.getByRole("list", { name: "Extracted memories" }).getByRole("listitem")

  // The AI works in the background after the memory is saved, so reopen the
  // dialog until its items have been stored
  const openExtracted = async (page: Page) => {
    await expect(async () => {
      await page.goto("/memories")
      const row = page.getByRole("row").filter({ hasText: memoryTitle })
      await row.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Manage Files" }).click()
      await expect(extractedItems(page).first()).toBeVisible({ timeout: 3000 })
    }).toPass({ timeout: 60_000 })
  }

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email, password)
    await page.goto("/memories")

    memoryTitle = randomMemoryTitle()
    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill(memoryTitle)
    await page
      .getByRole("textbox", { name: "Memory", exact: true })
      .fill("He fished at dawn. He sang in the boat.")
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()
    await expect(page.getByRole("dialog")).not.toBeVisible()

    await openExtracted(page)
  })

  test("Items start unconfirmed", async ({ page }) => {
    await expect(
      extractedItems(page).getByText("Confirmed", { exact: true }),
    ).toHaveCount(0)
    await expect(
      page.getByRole("button", { name: "Confirm all" }),
    ).toBeVisible()
  })

  test("Confirm and unconfirm one item", async ({ page }) => {
    const first = extractedItems(page).first()

    await first
      .getByRole("button", { name: "Confirm extracted memory" })
      .click()
    await expect(first.getByText("Confirmed", { exact: true })).toBeVisible()

    await first
      .getByRole("button", { name: "Unconfirm extracted memory" })
      .click()
    await expect(
      first.getByText("Confirmed", { exact: true }),
    ).not.toBeVisible()
  })

  test("Confirm all confirms every item", async ({ page }) => {
    const items = extractedItems(page)
    const count = await items.count()

    await page.getByRole("button", { name: "Confirm all" }).click()

    await expect(page.getByText(/items? confirmed/)).toBeVisible()
    await expect(items.getByText("Confirmed", { exact: true })).toHaveCount(
      count,
    )
    await expect(
      page.getByRole("button", { name: "Confirm all" }),
    ).not.toBeVisible()
  })

  test("A rejected item cannot be confirmed", async ({ page }) => {
    const first = extractedItems(page).first()

    await first.getByRole("button", { name: "Reject extracted memory" }).click()

    await expect(first.getByText("Rejected", { exact: true })).toBeVisible()
    await expect(
      first.getByRole("button", { name: "Confirm extracted memory" }),
    ).not.toBeVisible()
  })
})
