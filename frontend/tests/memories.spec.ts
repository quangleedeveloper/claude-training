import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import {
  randomEmail,
  randomMemoryContent,
  randomMemoryTitle,
  randomPassword,
} from "./utils/random"
import { logInUser } from "./utils/user"

test("Memories page is accessible and shows correct title", async ({
  page,
}) => {
  await page.goto("/memories")
  await expect(page.getByRole("heading", { name: "Memories" })).toBeVisible()
  await expect(
    page.getByText("Preserve and manage your memories"),
  ).toBeVisible()
})

test("Add Memory button is visible", async ({ page }) => {
  await page.goto("/memories")
  await expect(page.getByRole("button", { name: "Add Memory" })).toBeVisible()
})

test.describe("Memories management", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string
  const password = randomPassword()

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email, password)
    await page.goto("/memories")
  })

  test("Create a new memory successfully", async ({ page }) => {
    const title = randomMemoryTitle()
    const content = randomMemoryContent()

    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill(title)
    await page.getByRole("textbox", { name: "Memory *" }).fill(content)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Memory created successfully")).toBeVisible()
    await expect(page.getByText(title)).toBeVisible()
    await expect(page.getByText(content)).toBeVisible()
  })

  test("The memory form has no person field and the table says Not linked", async ({
    page,
  }) => {
    const title = randomMemoryTitle()

    await page.getByRole("button", { name: "Add Memory" }).click()
    await expect(page.getByRole("textbox", { name: "Person" })).toHaveCount(0)
    await page.getByRole("textbox", { name: "Title" }).fill(title)
    await page
      .getByRole("textbox", { name: "Memory *" })
      .fill(randomMemoryContent())
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()

    const row = page.getByRole("row").filter({ hasText: title })
    await expect(row).toContainText("Not linked")
  })

  test("Cancel memory creation", async ({ page }) => {
    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill("Test Memory")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
  })

  test("Title is required", async ({ page }) => {
    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill("")
    await page.getByRole("textbox", { name: "Title" }).blur()

    await expect(page.getByText("Title is required")).toBeVisible()
  })

  test.describe("Edit and Delete", () => {
    let memoryTitle: string

    test.beforeEach(async ({ page }) => {
      memoryTitle = randomMemoryTitle()

      await page.getByRole("button", { name: "Add Memory" }).click()
      await page.getByRole("textbox", { name: "Title" }).fill(memoryTitle)
      await page
        .getByRole("textbox", { name: "Memory *" })
        .fill(randomMemoryContent())
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page.getByText("Memory created successfully")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()
    })

    test("Edit a memory successfully", async ({ page }) => {
      const memoryRow = page.getByRole("row").filter({ hasText: memoryTitle })
      await memoryRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Edit Memory" }).click()

      const updatedTitle = randomMemoryTitle()
      await page.getByRole("textbox", { name: "Title" }).fill(updatedTitle)
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Memory updated successfully")).toBeVisible()
      await expect(page.getByText(updatedTitle)).toBeVisible()
    })

    test("Delete a memory successfully", async ({ page }) => {
      const memoryRow = page.getByRole("row").filter({ hasText: memoryTitle })
      await memoryRow.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Delete Memory" }).click()

      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The memory was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByText(memoryTitle)).not.toBeVisible()
    })
  })
})

test.describe("Memories empty state", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Shows empty state message when no memories exist", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/memories")

    await expect(
      page.getByText("You don't have any memories yet"),
    ).toBeVisible()
    await expect(page.getByText("Add a memory to get started")).toBeVisible()
  })
})
