import { expect, type Page, test } from "@playwright/test"
import { LoginService, PersonsService } from "../src/client"
import { createClient, createConfig } from "../src/client/client"
import { type Persona, seedPersona } from "./utils/persona"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword, randomPersonName } from "./utils/random"
import { logInUser } from "./utils/user"

// The backend must run with AI_BACKEND=fake so the seeded story is read without
// Ollama. Each test gets its own owner, member and persona.

const SAME_ANSWER =
  "If an account exists for that email it can now talk with this persona."

const apiFor = async (email: string, password: string) => {
  const baseURL = `${process.env.VITE_API_URL}`
  const login = await LoginService.loginAccessToken({
    client: createClient(createConfig({ baseURL })),
    body: { username: email, password },
  })
  return createClient(
    createConfig({ baseURL, auth: () => login.data.access_token }),
  )
}

test.describe("Sharing", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  const password = randomPassword()
  let ownerEmail: string
  let memberEmail: string
  let persona: Persona

  const openShare = async (page: Page) => {
    await page.goto("/persons")
    await page.getByRole("button", { name: "Person actions" }).click()
    await page.getByRole("menuitem", { name: "Share" }).click()
    await expect(page.getByRole("dialog")).toBeVisible()
  }

  const invite = async (email: string) => {
    const owner = await apiFor(ownerEmail, password)
    await PersonsService.inviteMember({
      client: owner,
      path: { id: persona.personId },
      body: { email, adult_confirmed: true },
    })
  }

  test.beforeEach(async () => {
    ownerEmail = randomEmail()
    memberEmail = randomEmail()
    await createUser({ email: ownerEmail, password })
    await createUser({ email: memberEmail, password })
    persona = await seedPersona({
      email: ownerEmail,
      password,
      personName: randomPersonName(),
    })
  })

  test("Invite stays disabled until the age tick is set", async ({ page }) => {
    await logInUser(page, ownerEmail, password)
    await openShare(page)
    const dialog = page.getByRole("dialog")

    await dialog.getByRole("textbox", { name: "Email" }).fill(memberEmail)
    await expect(dialog.getByRole("button", { name: "Invite" })).toBeDisabled()

    await dialog
      .getByRole("checkbox", { name: "I confirm this person is 18 or older" })
      .check()
    await expect(dialog.getByRole("button", { name: "Invite" })).toBeEnabled()
  })

  test("Known and unknown emails get the same confirmation", async ({
    page,
  }) => {
    await logInUser(page, ownerEmail, password)
    await openShare(page)
    const dialog = page.getByRole("dialog")

    for (const email of [memberEmail, randomEmail()]) {
      await dialog.getByRole("textbox", { name: "Email" }).fill(email)
      await dialog
        .getByRole("checkbox", { name: "I confirm this person is 18 or older" })
        .check()
      await dialog.getByRole("button", { name: "Invite" }).click()
      await expect(dialog.getByRole("status")).toHaveText(SAME_ANSWER)
      await dialog.getByRole("textbox", { name: "Email" }).fill("")
    }
  })

  test("The members list shows who was invited", async ({ page }) => {
    await invite(memberEmail)
    await logInUser(page, ownerEmail, password)
    await openShare(page)

    const members = page.getByRole("list", { name: "Members" })
    await expect(members).toContainText(memberEmail)
    await expect(members.getByRole("button", { name: "Revoke" })).toBeVisible()
  })

  test("Revoke explains what ends, then removes the member", async ({
    page,
  }) => {
    await invite(memberEmail)
    await logInUser(page, ownerEmail, password)
    await openShare(page)
    const dialog = page.getByRole("dialog")

    await dialog.getByRole("button", { name: "Revoke" }).click()
    await expect(dialog).toContainText("Their open chat ends")
    await expect(dialog).toContainText("is deleted")
    await dialog.getByRole("button", { name: "Keep access" }).click()
    await expect(dialog).toContainText(memberEmail)

    await dialog.getByRole("button", { name: "Revoke" }).click()
    await dialog.getByRole("button", { name: "Confirm revoke" }).click()
    await expect(dialog).toContainText("Nobody else can talk with this persona")
  })

  test("Shared with me lists the person by name and opens the chat", async ({
    page,
  }) => {
    await invite(memberEmail)
    await logInUser(page, memberEmail, password)
    await page.goto("/shared")

    const shared = page.getByRole("list", { name: "Shared with me" })
    await expect(shared).toContainText(persona.personName)
    await shared.getByRole("link", { name: "Talk" }).click()
    await expect(page).toHaveURL(new RegExp(`/chat/${persona.personId}`))
    await expect(page.getByRole("note")).toBeVisible()
  })

  test("Shared with me shows an empty state when nothing is shared", async ({
    page,
  }) => {
    await logInUser(page, memberEmail, password)
    await page.goto("/shared")

    await expect(page.getByText("Nothing is shared with you yet")).toBeVisible()
  })

  test("A revoked member loses the person and a chat left open says so", async ({
    page,
  }) => {
    await invite(memberEmail)
    await logInUser(page, memberEmail, password)
    await page.goto(`/chat/${persona.personId}`)
    await expect(page.getByRole("note")).toBeVisible()

    const owner = await apiFor(ownerEmail, password)
    const members = (
      await PersonsService.readMembers({
        client: owner,
        path: { id: persona.personId },
      })
    ).data.data
    for (const member of members) {
      await PersonsService.revokeMember({
        client: owner,
        path: { id: persona.personId, user_id: member.user_id },
      })
    }

    await page
      .getByRole("textbox", { name: "Your message" })
      .fill("Are you there?")
    await page.getByRole("button", { name: "Send" }).click()
    await expect(page.getByRole("alert")).toContainText(
      "You no longer have access to this conversation.",
    )

    await page.goto("/shared")
    await expect(page.getByText("Nothing is shared with you yet")).toBeVisible()
  })
})
