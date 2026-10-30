import { expect, type Page, test } from "@playwright/test"
import { LoginService, PersonsService } from "../src/client"
import { createClient, createConfig } from "../src/client/client"
import { createUser } from "./utils/privateApi"
import {
  randomEmail,
  randomMemoryContent,
  randomMemoryTitle,
  randomPassword,
  randomPersonName,
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
    await page
      .getByRole("textbox", { name: "Memory", exact: true })
      .fill(content)
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Memory created successfully")).toBeVisible()
    await expect(page.getByText(title)).toBeVisible()
    await expect(page.getByText(content)).toBeVisible()
  })

  test("The Memory field is a text editor that keeps its formatting", async ({
    page,
  }) => {
    const title = randomMemoryTitle()

    await page.getByRole("button", { name: "Add Memory" }).click()
    await expect(page.getByRole("toolbar")).toBeVisible()
    await page.getByRole("textbox", { name: "Title" }).fill(title)

    const editor = page.getByRole("textbox", { name: "Memory", exact: true })
    await editor.click()
    await page.getByRole("button", { name: "Bold" }).click()
    await page.keyboard.type("Dawn fishing")
    await page.getByRole("button", { name: "Bold" }).click()
    await page.keyboard.type(" with Grandpa")
    await page.keyboard.press("Enter")
    await page.getByRole("button", { name: "Bulleted list" }).click()
    await page.keyboard.type("A thermos of tea")
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()

    // The table shows the words, not the Markdown marks
    const row = page.getByRole("row").filter({ hasText: title })
    await expect(row).toContainText("Dawn fishing with Grandpa")
    await expect(row).not.toContainText("**")

    // Reopening shows the formatting again
    await row.getByRole("button").last().click()
    await page.getByRole("menuitem", { name: "Edit Memory" }).click()
    const reopened = page.getByRole("textbox", { name: "Memory", exact: true })
    await expect(reopened.locator("strong")).toHaveText("Dawn fishing")
    await expect(reopened.locator("ul li")).toHaveText("A thermos of tea")
  })

  test("The Memory editor is required", async ({ page }) => {
    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill(randomMemoryTitle())
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Memory is required")).toBeVisible()
  })

  test("Plain text in an older memory opens in the editor", async ({
    page,
  }) => {
    const title = randomMemoryTitle()
    const content = "He woke us up before dawn every summer."

    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill(title)
    await page
      .getByRole("textbox", { name: "Memory", exact: true })
      .fill(content)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()

    const row = page.getByRole("row").filter({ hasText: title })
    await row.getByRole("button").last().click()
    await page.getByRole("menuitem", { name: "Edit Memory" }).click()
    await expect(
      page.getByRole("textbox", { name: "Memory", exact: true }),
    ).toHaveText(content)
  })

  const createPerson = async (name: string) => {
    const baseURL = `${process.env.VITE_API_URL}`
    const login = await LoginService.loginAccessToken({
      client: createClient(createConfig({ baseURL })),
      body: { username: email, password },
    })
    await PersonsService.createPerson({
      client: createClient(
        createConfig({ baseURL, auth: () => login.data.access_token }),
      ),
      body: { name, other_names: [] },
    })
  }

  const fillMemory = async (page: Page, title: string) => {
    await page.getByRole("textbox", { name: "Title" }).fill(title)
    await page
      .getByRole("textbox", { name: "Memory", exact: true })
      .fill(randomMemoryContent())
  }

  test("Without a person the table says Not linked", async ({ page }) => {
    const title = randomMemoryTitle()

    await page.getByRole("button", { name: "Add Memory" }).click()
    await expect(page.getByRole("combobox", { name: "Person" })).toHaveText(
      "No person",
    )
    await fillMemory(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()

    const row = page.getByRole("row").filter({ hasText: title })
    await expect(row).toContainText("Not linked")
  })

  test("Add Memory lists the people and links the chosen one", async ({
    page,
  }) => {
    const personName = randomPersonName()
    const title = randomMemoryTitle()
    await createPerson(personName)
    await page.reload()

    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("combobox", { name: "Person" }).click()
    await page.getByRole("option", { name: personName }).click()
    await fillMemory(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()

    const row = page.getByRole("row").filter({ hasText: title })
    await expect(row).toContainText(personName)
  })

  test("Edit Memory shows the current person and can change or clear it", async ({
    page,
  }) => {
    const personName = randomPersonName()
    const title = randomMemoryTitle()
    await createPerson(personName)
    await page.reload()

    await page.getByRole("button", { name: "Add Memory" }).click()
    await fillMemory(page, title)
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()

    const row = page.getByRole("row").filter({ hasText: title })
    const edit = async () => {
      await row.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Edit Memory" }).click()
    }

    await edit()
    await expect(page.getByRole("combobox", { name: "Person" })).toHaveText(
      "No person",
    )
    await page.getByRole("combobox", { name: "Person" }).click()
    await page.getByRole("option", { name: personName }).click()
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory updated successfully")).toBeVisible()
    await expect(row).toContainText(personName)

    await edit()
    await expect(page.getByRole("combobox", { name: "Person" })).toHaveText(
      personName,
    )
    await page.getByRole("combobox", { name: "Person" }).click()
    await page.getByRole("option", { name: "No person" }).click()
    await page.getByRole("button", { name: "Save" }).click()
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
        .getByRole("textbox", { name: "Memory", exact: true })
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
