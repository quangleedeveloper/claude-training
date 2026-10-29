// Seeds a persona for the chat tests through the API, with its own client so tests
// running in parallel do not share a token. The backend must run with
// AI_BACKEND=fake: it extracts one fact per sentence, without waiting for Ollama.
import {
  ExtractedMemoriesService,
  LoginService,
  MemoriesService,
  PersonsService,
} from "../../src/client"
import { createClient, createConfig } from "../../src/client/client"

export const FACT = "Grandpa fished at dawn."

export type Persona = {
  personId: string
  personName: string
  fact: string
}

export async function seedPersona({
  email,
  password,
  personName,
}: {
  email: string
  password: string
  personName: string
}): Promise<Persona> {
  const baseURL = `${process.env.VITE_API_URL}`
  const anonymous = createClient(createConfig({ baseURL }))
  const login = await LoginService.loginAccessToken({
    client: anonymous,
    body: { username: email, password },
  })
  const client = createClient(
    createConfig({ baseURL, auth: () => login.data.access_token }),
  )

  const person = (
    await PersonsService.createPerson({
      client,
      body: { name: personName, other_names: [] },
    })
  ).data
  const memory = (
    await MemoriesService.createMemory({
      client,
      body: { title: "Fishing", person_name: personName, content: FACT },
    })
  ).data
  await MemoriesService.linkMemoryPerson({
    client,
    path: { id: memory.id },
    body: { person_id: person.id },
  })

  // The AI reads the story in the background: wait for its items, then confirm them,
  // because the persona only uses what the family confirmed
  let items = (
    await ExtractedMemoriesService.readExtractedMemories({
      client,
      path: { memory_id: memory.id },
    })
  ).data.data
  for (let attempt = 0; items.length === 0 && attempt < 40; attempt++) {
    await new Promise((resolve) => setTimeout(resolve, 500))
    items = (
      await ExtractedMemoriesService.readExtractedMemories({
        client,
        path: { memory_id: memory.id },
      })
    ).data.data
  }
  if (items.length === 0) {
    throw new Error("The story was not read in time; is AI_BACKEND=fake set?")
  }
  for (const item of items) {
    await ExtractedMemoriesService.confirmExtractedMemory({
      client,
      path: { memory_id: memory.id, extracted_id: item.id },
    })
  }
  return { personId: person.id, personName, fact: FACT }
}
