import { expect, type Page, test } from "@playwright/test"
import { FACT, type Persona, seedPersona } from "./utils/persona"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword, randomPersonName } from "./utils/random"
import { logInUser } from "./utils/user"

// The backend must run with AI_BACKEND=fake: replies are canned ("Fake answer citing
// [1].") and the story is read without waiting for Ollama. Tests that need a reply the
// fake never gives (a bad citation, an error, a 403) answer the request from the page.

const MESSAGES = "**/api/v1/conversations/*/messages"

const sse = (events: { name: string; data: object }[]) =>
  events
    .map(
      ({ name, data }) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`,
    )
    .join("")

const done = (overrides: object = {}) => ({
  name: "done",
  data: {
    sources: [],
    fallback: false,
    notice: "notice",
    cited_ids: [],
    invalid_citations: [],
    uncited: false,
    ...overrides,
  },
})

const source = (content: string) => ({
  item: { id: "11111111-1111-1111-1111-111111111111", content },
  memory_title: "Fishing",
  person_name: "Grandpa",
  score: 0.9,
})

test.describe("Chat window", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  const password = randomPassword()
  let email: string
  let persona: Persona

  const input = (page: Page) =>
    page.getByRole("textbox", { name: "Your message" })
  const log = (page: Page) => page.getByRole("log", { name: "Conversation" })

  const send = async (page: Page, text: string) => {
    await input(page).fill(text)
    await page.getByRole("button", { name: "Send" }).click()
  }

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
    persona = await seedPersona({
      email,
      password,
      personName: randomPersonName(),
    })
  })

  test.beforeEach(async ({ page }) => {
    await logInUser(page, email, password)
    await page.goto(`/chat/${persona.personId}`)
    await expect(page.getByRole("note")).toBeVisible()
  })

  test("Notice stays visible", async ({ page }) => {
    await expect(page.getByRole("note")).toContainText("AI recreation")

    await send(page, persona.fact)
    await expect(log(page)).toContainText("Fake answer")

    await expect(page.getByRole("note")).toBeVisible()
    await expect(page.getByRole("note")).toContainText("AI recreation")
  })

  test("Reply streams in", async ({ page }) => {
    await expect(log(page)).toHaveAttribute("aria-live", "polite")
    await page.route(MESSAGES, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 800))
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([
          { name: "token", data: { text: "Hello " } },
          { name: "token", data: { text: "there." } },
          done({ fallback: true }),
        ]),
      })
    })

    await send(page, "Hi")

    // The question is on screen at once and nothing more can be sent meanwhile
    await expect(log(page)).toContainText("Hi")
    await expect(input(page)).toBeDisabled()
    await expect(log(page)).toContainText("Hello there.")
    await expect(input(page)).toBeEnabled()
  })

  test("Citations link to sources", async ({ page }) => {
    await send(page, persona.fact)

    const link = log(page).getByRole("link", { name: "[1]" })
    await expect(link).toBeVisible()
    await link.click()
    const first = page
      .getByRole("list", { name: "Sources" })
      .getByRole("listitem")
      .first()
    await expect(first).toBeFocused()
    await expect(first).toContainText(FACT)
  })

  test("A citation without a source stays plain text", async ({ page }) => {
    await page.route(MESSAGES, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([
          { name: "token", data: { text: "He fished [1] and sang [9]." } },
          done({
            sources: [source("He fished at dawn.")],
            cited_ids: ["11111111-1111-1111-1111-111111111111"],
            invalid_citations: [9],
          }),
        ]),
      }),
    )

    await send(page, "Tell me")

    await expect(log(page).getByRole("link", { name: "[1]" })).toBeVisible()
    await expect(log(page)).toContainText("[9]")
    await expect(log(page).getByRole("link", { name: "[9]" })).toHaveCount(0)
  })

  test("No-memory and uncited replies", async ({ page }) => {
    await send(page, "What did you think of my wedding?")
    await expect(log(page)).toContainText("I don't remember that.")
    await expect(page.getByRole("list", { name: "Sources" })).toHaveCount(0)
    await expect(log(page)).not.toContainText("not backed by a memory")

    await page.route(MESSAGES, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([
          { name: "token", data: { text: "I think so." } },
          done({ sources: [source("He fished at dawn.")], uncited: true }),
        ]),
      }),
    )
    await send(page, "Did he fish?")
    await expect(log(page)).toContainText(
      "This reply is not backed by a memory.",
    )
  })

  test("Errors keep the typed text", async ({ page }) => {
    await page.route(MESSAGES, (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: sse([
          { name: "token", data: { text: "Half a" } },
          { name: "error", data: { detail: "database password leaked" } },
        ]),
      }),
    )

    await send(page, "Please answer")

    await expect(page.getByRole("alert")).toContainText(
      "Something went wrong. Please try again.",
    )
    await expect(page.getByText("database password leaked")).toHaveCount(0)
    await expect(log(page)).not.toContainText("Half a")
    await expect(log(page)).toContainText("Not answered")
    await expect(input(page)).toHaveValue("Please answer")

    await page.unroute(MESSAGES)
    await page.route(MESSAGES, (route) => route.abort())
    await page.getByRole("button", { name: "Send" }).click()
    await expect(page.getByRole("alert")).toContainText("Something went wrong")
    await expect(input(page)).toHaveValue("Please answer")
  })

  test("End conversation", async ({ page }) => {
    await send(page, persona.fact)
    await expect(log(page)).toContainText("Fake answer")

    await page.getByRole("button", { name: "End conversation" }).click()
    await expect(page.getByRole("dialog")).toContainText("will be deleted")
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "End conversation" })
      .click()

    await expect(page.getByText("The conversation has ended")).toBeVisible()
    await page.waitForURL("/persons")
  })

  test("Access removed", async ({ page }) => {
    await page.route(MESSAGES, (route) =>
      route.fulfill({
        status: 403,
        json: { detail: "Not enough permissions" },
      }),
    )

    await send(page, "Hello")

    await expect(page.getByRole("alert")).toContainText(
      "You no longer have access to this conversation.",
    )
    await expect(input(page)).toBeDisabled()
    await expect(page.getByRole("button", { name: "Send" })).toBeDisabled()
    // Not sent back to the login page: losing access is not losing the session
    await expect(page).toHaveURL(/\/chat\//)
  })

  test("Conversation ended", async ({ page }) => {
    await page.route(MESSAGES, (route) =>
      route.fulfill({
        status: 409,
        json: { detail: "Conversation has ended" },
      }),
    )

    await send(page, "Hello")

    await expect(page.getByRole("alert")).toContainText(
      "This conversation has ended.",
    )
    await expect(page.getByRole("button", { name: "Send" })).toBeDisabled()
  })

  test("Nothing stored in the browser", async ({ page }) => {
    const consoleText: string[] = []
    page.on("console", (message) => consoleText.push(message.text()))

    await send(page, persona.fact)
    await expect(log(page)).toContainText("Fake answer")

    const stored = await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    )
    for (const secret of [persona.fact, "Fake answer", "Grandpa"]) {
      expect(stored).not.toContain(secret)
      expect(page.url()).not.toContain(secret)
      expect(consoleText.join("\n")).not.toContain(secret)
    }
  })
})
