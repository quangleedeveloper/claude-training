export const randomEmail = () =>
  `test_${Math.random().toString(36).substring(7)}@example.com`

export const randomTeamName = () =>
  `Team ${Math.random().toString(36).substring(7)}`

export const randomPassword = () => `${Math.random().toString(36).substring(2)}`

export const slugify = (text: string) =>
  text
    .toLowerCase()
    .replace(/\s+/g, "-")
    .replace(/[^\w-]+/g, "")

export const randomItemTitle = () =>
  `Item ${Math.random().toString(36).substring(7)}`

export const randomItemDescription = () =>
  `Description ${Math.random().toString(36).substring(7)}`

export const randomMemoryTitle = () =>
  `Memory ${Math.random().toString(36).substring(7)}`

export const randomMemoryContent = () =>
  `Story ${Math.random().toString(36).substring(7)}`

export const randomPersonName = () =>
  `Person ${Math.random().toString(36).substring(7)}`
