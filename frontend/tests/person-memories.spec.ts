import { expect, type Page, test } from "@playwright/test"
import { LoginService, MemoriesService, PersonsService } from "../src/client"
import { createClient, createConfig } from "../src/client/client"
import { type Persona, seedPersona } from "./utils/persona"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword, randomPersonName } from "./utils/random"
import { logInUser } from "./utils/user"

// The backend must run with AI_BACKEND=fake so the seeded story is read without
// Ollama. Each test gets its own user, so lists are never shared.

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

test.describe("Memories of a person", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  const password = randomPassword()
  let email: string
  let persona: Persona

  const openMemories = async (page: Page, personName: string) => {
    await page.goto("/persons")
    const row = page.getByRole("row", { name: new RegExp(personName) })
    await row.getByRole("button", { name: "Person actions" }).click()
    await page.getByRole("menuitem", { name: "Memories" }).click()
    await expect(page.getByRole("dialog")).toBeVisible()
  }

  test.beforeEach(async () => {
    email = randomEmail()
    await createUser({ email, password })
    persona = await seedPersona({
      email,
      password,
      personName: randomPersonName(),
    })
  })

  test("Lists the memories linked to the person, not the others", async ({
    page,
  }) => {
    const client = await apiFor(email, password)
    await MemoriesService.createMemory({
      client,
      body: {
        title: "Not linked to anyone",
        person_name: "Somebody else",
        content: "A story about nobody in particular.",
      },
    })
    await logInUser(page, email, password)
    await openMemories(page, persona.personName)

    const linked = page.getByRole("list", { name: "Linked memories" })
    await expect(linked).toContainText("Fishing")
    await expect(linked.getByRole("listitem")).toHaveCount(1)
    await expect(page.getByRole("dialog")).toContainText("1 memory")
    await expect(page.getByRole("dialog")).not.toContainText(
      "Not linked to anyone",
    )
  })

  test("Shows an empty state for a person with no linked memories", async ({
    page,
  }) => {
    const client = await apiFor(email, password)
    const lonely = randomPersonName()
    await PersonsService.createPerson({
      client,
      body: { name: lonely, other_names: [] },
    })
    await logInUser(page, email, password)
    await openMemories(page, lonely)

    await expect(page.getByRole("dialog")).toContainText(
      "No memories are linked to this person yet",
    )
  })

  test("Only the signed-in user's memories are asked for", async ({ page }) => {
    const urls: string[] = []
    page.on("request", (request) => {
      if (request.url().includes("/memories")) urls.push(request.url())
    })
    await logInUser(page, email, password)
    await openMemories(page, persona.personName)
    await expect(
      page.getByRole("list", { name: "Linked memories" }),
    ).toBeVisible()

    expect(
      urls.some((url) => url.includes(`person_id=${persona.personId}`)),
    ).toBe(true)
  })
})
