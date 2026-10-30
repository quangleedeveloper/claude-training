import { expect, type Page, test } from "@playwright/test"
import { type Persona, seedPersona } from "./utils/persona"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword, randomPersonName } from "./utils/random"
import { logInUser } from "./utils/user"

// The backend must run with AI_BACKEND=fake: the note written when a chat ends is
// canned, so no model is needed. Each test seeds its own persona and user.

test.describe("Recall panel", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  const password = randomPassword()
  let email: string
  let persona: Persona

  const panel = (page: Page) =>
    page.getByRole("region", { name: "What we talked about" })

  // Say something and end the chat, which keeps a note for the next one
  const talkAndEnd = async (page: Page) => {
    await page.goto(`/chat/${persona.personId}`)
    await expect(page.getByRole("note")).toBeVisible()
    await page.getByRole("textbox", { name: "Your message" }).fill(persona.fact)
    await page.getByRole("button", { name: "Send" }).click()
    await expect(page.getByRole("log", { name: "Conversation" })).toContainText(
      "Fake answer",
    )
    await page.getByRole("button", { name: "End conversation" }).click()
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "End conversation" })
      .click()
    await page.waitForURL("/persons")
  }

  test.beforeEach(async ({ page }) => {
    email = randomEmail()
    await createUser({ email, password })
    persona = await seedPersona({
      email,
      password,
      personName: randomPersonName(),
    })
    await logInUser(page, email, password)
  })

  test("Nothing kept yet shows an empty state, not an error", async ({
    page,
  }) => {
    await page.goto(`/chat/${persona.personId}`)

    await expect(panel(page)).toContainText("Nothing is kept yet")
    await expect(panel(page).getByRole("alert")).toHaveCount(0)
    await expect(
      panel(page).getByRole("button", { name: "Delete note" }),
    ).toHaveCount(0)
  })

  test("My own note is shown after a conversation", async ({ page }) => {
    await talkAndEnd(page)
    await page.goto(`/chat/${persona.personId}`)

    await expect(panel(page)).not.toContainText("Nothing is kept yet")
    await expect(
      panel(page).getByRole("button", { name: "Delete note" }),
    ).toBeVisible()
  })

  test("Cancel keeps the note", async ({ page }) => {
    await talkAndEnd(page)
    await page.goto(`/chat/${persona.personId}`)

    await panel(page).getByRole("button", { name: "Delete note" }).click()
    await expect(page.getByRole("dialog")).toContainText("Delete this note?")
    await page.getByRole("button", { name: "Cancel" }).click()

    await expect(page.getByRole("dialog")).toHaveCount(0)
    await expect(
      panel(page).getByRole("button", { name: "Delete note" }),
    ).toBeVisible()
  })

  test("Deleting the note shows the empty state", async ({ page }) => {
    await talkAndEnd(page)
    await page.goto(`/chat/${persona.personId}`)

    await panel(page).getByRole("button", { name: "Delete note" }).click()
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Delete", exact: true })
      .click()

    await expect(panel(page)).toContainText("Nothing is kept yet")
    // Gone for good: a fresh load asks the API again and still finds nothing
    await page.reload()
    await expect(panel(page)).toContainText("Nothing is kept yet")
  })

  test("The panel asks only for the signed-in user's summary", async ({
    page,
  }) => {
    const urls: string[] = []
    page.on("request", (request) => {
      if (request.url().includes("/summary")) urls.push(request.url())
    })
    await page.goto(`/chat/${persona.personId}`)
    await expect(panel(page)).toContainText("Nothing is kept yet")

    expect(urls.length).toBeGreaterThan(0)
    for (const url of urls) {
      expect(url).toContain(`/persons/${persona.personId}/summary`)
      expect(url).not.toContain("user")
    }
  })
})
