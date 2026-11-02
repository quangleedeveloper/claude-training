import { expect, type Page, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import {
  randomEmail,
  randomMemoryContent,
  randomMemoryTitle,
  randomPassword,
  randomPersonName,
} from "./utils/random"
import { logInUser } from "./utils/user"

test("People page is accessible and shows correct title", async ({ page }) => {
  await page.goto("/persons")
  await expect(page.getByRole("heading", { name: "People" })).toBeVisible()
  await expect(page.getByText("The people your family remembers")).toBeVisible()
})

test("Add Person button is visible", async ({ page }) => {
  await page.goto("/persons")
  await expect(page.getByRole("button", { name: "Add Person" })).toBeVisible()
})

async function addPerson(page: Page, name: string, otherNames = "") {
  await page.getByRole("button", { name: "Add Person" }).click()
  await page.getByRole("textbox", { name: "Name *" }).fill(name)
  if (otherNames) {
    await page.getByRole("textbox", { name: "Other names" }).fill(otherNames)
  }
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Person created successfully")).toBeVisible()
  await expect(page.getByRole("dialog")).not.toBeVisible()
}

test.describe("People management", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string
  const password = randomPassword()

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email, password)
    await page.goto("/persons")
  })

  test("Create a new person successfully", async ({ page }) => {
    const name = randomPersonName()

    await addPerson(page, name, "Mom, Mẹ")

    const row = page.getByRole("row").filter({ hasText: name })
    await expect(row).toBeVisible()
    await expect(row.getByText("Mom, Mẹ")).toBeVisible()
  })

  test("Cancel person creation", async ({ page }) => {
    await page.getByRole("button", { name: "Add Person" }).click()
    await page.getByRole("textbox", { name: "Name *" }).fill("Cancelled Person")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).not.toBeVisible()
    await expect(page.getByText("Cancelled Person")).not.toBeVisible()
  })

  test("Name is required", async ({ page }) => {
    await page.getByRole("button", { name: "Add Person" }).click()
    await page.getByRole("textbox", { name: "Name *" }).fill("")
    await page.getByRole("textbox", { name: "Name *" }).blur()

    await expect(page.getByText("Name is required")).toBeVisible()
  })

  test("Too many other names is refused", async ({ page }) => {
    await page.getByRole("button", { name: "Add Person" }).click()
    await page.getByRole("textbox", { name: "Name *" }).fill(randomPersonName())
    await page
      .getByRole("textbox", { name: "Other names" })
      .fill("a, b, c, d, e, f, g, h, i, j, k")
    await page.getByRole("textbox", { name: "Other names" }).blur()

    await expect(page.getByText("At most 10 other names")).toBeVisible()
  })

  test.describe("Edit and Delete", () => {
    let personName: string

    test.beforeEach(async ({ page }) => {
      personName = randomPersonName()
      await addPerson(page, personName, "Mum")
    })

    test("Edit a person successfully", async ({ page }) => {
      const row = page.getByRole("row").filter({ hasText: personName })
      await row.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Edit Person" }).click()

      const updatedName = randomPersonName()
      await page.getByRole("textbox", { name: "Name *" }).fill(updatedName)
      await page.getByRole("textbox", { name: "Other names" }).fill("Nana")
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Person updated successfully")).toBeVisible()
      const updatedRow = page.getByRole("row").filter({ hasText: updatedName })
      await expect(updatedRow).toBeVisible()
      await expect(updatedRow.getByText("Nana")).toBeVisible()
    })

    test("Delete a person successfully", async ({ page }) => {
      const row = page.getByRole("row").filter({ hasText: personName })
      await row.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Delete Person" }).click()
      await page.getByRole("button", { name: "Delete" }).click()

      await expect(
        page.getByText("The person was deleted successfully"),
      ).toBeVisible()
      await expect(page.getByText(personName)).not.toBeVisible()
    })
  })

  test.describe("Linking memories", () => {
    let personName: string
    let memoryTitle: string

    const openLinkDialog = async (page: Page) => {
      await page.goto("/memories")
      const row = page.getByRole("row").filter({ hasText: memoryTitle })
      await row.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Link Person" }).click()
    }

    test.beforeEach(async ({ page }) => {
      personName = randomPersonName()
      memoryTitle = randomMemoryTitle()
      await addPerson(page, personName)

      await page.goto("/memories")
      await page.getByRole("button", { name: "Add Memory" }).click()
      await page.getByRole("textbox", { name: "Title" }).fill(memoryTitle)
      await page
        .getByRole("textbox", { name: "Memory", exact: true })
        .fill(randomMemoryContent())
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page.getByText("Memory created successfully")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()
    })

    test("Link a memory to a person and unlink it", async ({ page }) => {
      await openLinkDialog(page)
      await expect(page.getByRole("combobox")).toHaveText("No person")
      await page.getByRole("combobox").click()
      await page.getByRole("option", { name: personName }).click()
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Memory linked to person")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()

      // The table names the linked person, not a typed label
      const row = page.getByRole("row").filter({ hasText: memoryTitle })
      await expect(row).toContainText(personName)

      // Linking is saved: the dialog shows the person after a reload
      await page.reload()
      await openLinkDialog(page)
      await expect(page.getByRole("combobox")).toHaveText(personName)

      await page.getByRole("combobox").click()
      await page.getByRole("option", { name: "No person" }).click()
      await page.getByRole("button", { name: "Save" }).click()

      await expect(page.getByText("Memory unlinked from person")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()
      await expect(
        page.getByRole("row").filter({ hasText: memoryTitle }),
      ).toContainText("Not linked")
    })

    test("Deleting a person keeps its memories, unlinked", async ({ page }) => {
      await openLinkDialog(page)
      await page.getByRole("combobox").click()
      await page.getByRole("option", { name: personName }).click()
      await page.getByRole("button", { name: "Save" }).click()
      await expect(page.getByText("Memory linked to person")).toBeVisible()
      await expect(page.getByRole("dialog")).not.toBeVisible()

      await page.goto("/persons")
      const row = page.getByRole("row").filter({ hasText: personName })
      await row.getByRole("button").last().click()
      await page.getByRole("menuitem", { name: "Delete Person" }).click()
      await page.getByRole("button", { name: "Delete" }).click()
      await expect(
        page.getByText("The person was deleted successfully"),
      ).toBeVisible()

      await page.goto("/memories")
      await expect(page.getByText(memoryTitle)).toBeVisible()
      await openLinkDialog(page)
      await expect(page.getByRole("combobox")).toHaveText("No person")
    })
  })
})

test.describe("People empty state", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("Shows empty state message when no people exist", async ({ page }) => {
    const email = randomEmail()
    const password = randomPassword()
    await createUser({ email, password })
    await logInUser(page, email, password)

    await page.goto("/persons")

    await expect(page.getByText("You don't have any people yet")).toBeVisible()
    await expect(page.getByText("Add a person to get started")).toBeVisible()
  })
})
