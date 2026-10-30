import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import {
  randomEmail,
  randomMemoryContent,
  randomMemoryTitle,
  randomPassword,
} from "./utils/random"
import { logInUser } from "./utils/user"

// Smallest byte strings whose signatures the backend recognises
const pngBytes = () =>
  Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    Buffer.alloc(32),
  ])
const mp3Bytes = () =>
  Buffer.concat([
    Buffer.from("ID3"),
    Buffer.from([3, 0, 0, 0, 0, 0, 0]),
    Buffer.alloc(32),
  ])

const randomName = (extension: string) =>
  `${Math.random().toString(36).substring(7)}${extension}`

test.describe("Memory files", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  const password = randomPassword()
  let email: string
  let memoryTitle: string

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test.beforeEach(async ({ page }) => {
    memoryTitle = randomMemoryTitle()
    await logInUser(page, email, password)
    await page.goto("/memories")

    await page.getByRole("button", { name: "Add Memory" }).click()
    await page.getByRole("textbox", { name: "Title" }).fill(memoryTitle)
    await page
      .getByRole("textbox", { name: "Memory *" })
      .fill(randomMemoryContent())
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText("Memory created successfully")).toBeVisible()
    await expect(page.getByRole("dialog")).not.toBeVisible()

    const memoryRow = page.getByRole("row").filter({ hasText: memoryTitle })
    await memoryRow.getByRole("button", { name: "Memory actions" }).click()
    await page.getByRole("menuitem", { name: "Manage Files" }).click()
    await expect(
      page.getByRole("dialog", { name: `Files for ${memoryTitle}` }),
    ).toBeVisible()
  })

  test("Shows an empty state before any upload", async ({ page }) => {
    await expect(page.getByText("No files uploaded yet")).toBeVisible()
  })

  test("Upload photos and audio and see them processed", async ({ page }) => {
    const photo = randomName(".png")
    const recording = randomName(".mp3")

    await page.getByLabel("Photos, videos and audio").setInputFiles([
      { name: photo, mimeType: "image/png", buffer: pngBytes() },
      { name: recording, mimeType: "audio/mpeg", buffer: mp3Bytes() },
    ])
    await page.getByRole("button", { name: "Upload 2" }).click()

    await expect(page.getByText("2 files uploaded")).toBeVisible()
    for (const name of [photo, recording]) {
      const row = page.getByRole("row").filter({ hasText: name })
      await expect(row.getByText("Processed")).toBeVisible()
    }
  })

  test("Unsupported file types are rejected before uploading", async ({
    page,
  }) => {
    const notes = randomName(".txt")

    await page.getByLabel("Photos, videos and audio").setInputFiles({
      name: notes,
      mimeType: "text/plain",
      buffer: Buffer.from("just some notes"),
    })

    await expect(page.getByLabel("Files not uploaded")).toContainText(notes)
    await expect(page.getByLabel("Files not uploaded")).toContainText(
      "Unsupported file type",
    )
    await expect(page.getByRole("button", { name: "Upload" })).toBeDisabled()
  })

  test("A file whose content does not match its extension is rejected by the server", async ({
    page,
  }) => {
    const fake = randomName(".png")

    await page.getByLabel("Photos, videos and audio").setInputFiles({
      name: fake,
      mimeType: "image/png",
      buffer: Buffer.from("this is not really a png file"),
    })
    await page.getByRole("button", { name: "Upload 1" }).click()

    await expect(page.getByLabel("Files not uploaded")).toContainText(
      "does not match",
    )
    await expect(page.getByText("No files uploaded yet")).toBeVisible()
  })

  test("Delete an uploaded file", async ({ page }) => {
    const photo = randomName(".png")

    await page.getByLabel("Photos, videos and audio").setInputFiles({
      name: photo,
      mimeType: "image/png",
      buffer: pngBytes(),
    })
    await page.getByRole("button", { name: "Upload 1" }).click()
    const row = page.getByRole("row").filter({ hasText: photo })
    await expect(row.getByText("Processed")).toBeVisible()

    await row.getByRole("button", { name: `Delete file ${photo}` }).click()
    await page
      .getByRole("dialog", { name: "Delete File" })
      .getByRole("button", { name: "Delete" })
      .click()

    await expect(
      page.getByText("The file was deleted successfully"),
    ).toBeVisible()
    await expect(page.getByText(photo)).not.toBeVisible()
  })
})
