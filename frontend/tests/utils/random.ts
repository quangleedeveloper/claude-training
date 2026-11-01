export const randomEmail = () =>
  `test_${Math.random().toString(36).substring(7)}@example.com`

export const randomPassword = () => `${Math.random().toString(36).substring(2)}`

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
