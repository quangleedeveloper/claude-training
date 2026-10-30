import { expect, type Page, test } from "@playwright/test"
import { isAxiosError } from "axios"
import { LoginService, PersonsService } from "../src/client"
import { createClient, createConfig } from "../src/client/client"
import { type Persona, seedPersona } from "./utils/persona"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword, randomPersonName } from "./utils/random"
import { logInUser } from "./utils/user"

// The backend must run with AI_BACKEND=fake so an accepted offer is read without
// Ollama. Each test gets its own owner, member and persona.

const OFFER_TEXT = "She sang while she cooked."

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

test.describe("Offer a memory", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  const password = randomPassword()
  let ownerEmail: string
  let memberEmail: string
  let persona: Persona

  const offerFromMember = async (text = OFFER_TEXT) => {
    const client = await apiFor(memberEmail, password)
    await PersonsService.createOffer({
      client,
      path: { id: persona.personId },
      body: { content: text },
    })
  }

  const openOffers = async (page: Page) => {
    await page.goto("/persons")
    await page.getByRole("button", { name: "Person actions" }).click()
    await page.getByRole("menuitem", { name: "Offers" }).click()
    await expect(page.getByRole("dialog")).toBeVisible()
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
    const owner = await apiFor(ownerEmail, password)
    await PersonsService.inviteMember({
      client: owner,
      path: { id: persona.personId },
      body: { email: memberEmail, adult_confirmed: true },
    })
  })

  test("A member offers a memory and is told the family decides", async ({
    page,
  }) => {
    await logInUser(page, memberEmail, password)
    await page.goto(`/chat/${persona.personId}`)
    await page.getByRole("button", { name: "Offer a memory" }).click()

    await expect(page.getByRole("dialog")).toContainText(
      "The family decides whether it becomes a memory",
    )
    await page.getByRole("textbox", { name: "Your memory" }).fill(OFFER_TEXT)
    await page.getByRole("button", { name: "Send" }).click()

    await expect(page.getByRole("status")).toContainText(
      "Your offer was sent to the family.",
    )
  })

  test("A blank offer is refused before it is sent", async ({ page }) => {
    await logInUser(page, memberEmail, password)
    await page.goto(`/chat/${persona.personId}`)
    await page.getByRole("button", { name: "Offer a memory" }).click()
    await page.getByRole("button", { name: "Send" }).click()

    await expect(page.getByText("Write the memory first")).toBeVisible()
  })

  test("The owner sees the offer with Accept and Decline", async ({ page }) => {
    await offerFromMember()
    await logInUser(page, ownerEmail, password)
    await openOffers(page)

    const offer = page
      .getByRole("list", { name: "Offers" })
      .getByRole("listitem")
    await expect(offer).toContainText(OFFER_TEXT)
    await expect(offer.getByRole("button", { name: "Accept" })).toBeVisible()
    await expect(offer.getByRole("button", { name: "Decline" })).toBeVisible()
  })

  test("Accepting says the new memory is not yet confirmed", async ({
    page,
  }) => {
    await offerFromMember()
    await logInUser(page, ownerEmail, password)
    await openOffers(page)
    await page.getByRole("button", { name: "Accept" }).click()

    await expect(page.getByRole("status")).toContainText(
      "A new memory was created and is not yet confirmed",
    )
    await expect(page.getByText("No offers are waiting.")).toBeVisible()

    await page.getByRole("link", { name: "Open memories" }).click()
    await expect(page).toHaveURL(/\/memories/)
    await expect(page.getByText(`Offered: ${OFFER_TEXT}`)).toBeVisible()
  })

  test("Declining asks first, then the offer is gone", async ({ page }) => {
    await offerFromMember()
    await logInUser(page, ownerEmail, password)
    await openOffers(page)

    await page.getByRole("button", { name: "Decline" }).click()
    await expect(page.getByText("Decline this offer?")).toBeVisible()
    await page.getByRole("button", { name: "Keep" }).click()
    await expect(page.getByText(OFFER_TEXT)).toBeVisible()

    await page.getByRole("button", { name: "Decline" }).click()
    await page.getByRole("button", { name: "Confirm decline" }).click()
    await expect(page.getByText("No offers are waiting.")).toBeVisible()
  })

  test("A member has no offers list and the API refuses it", async ({
    page,
  }) => {
    await logInUser(page, memberEmail, password)
    await page.goto("/persons")
    // Members own no people, so there is no menu to open the list from
    await expect(
      page.getByRole("button", { name: "Person actions" }),
    ).toHaveCount(0)

    const client = await apiFor(memberEmail, password)
    const refused = await PersonsService.readOffers({
      client,
      path: { id: persona.personId },
    }).catch((error: unknown) => error)
    expect(isAxiosError(refused) && refused.response?.status).toBe(403)
  })
})
