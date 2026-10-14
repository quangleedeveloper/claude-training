# Memorial Robot

Memorial Robot is an AI robot designed to preserve memories and simulate the conversational abilities of the deceased.

## Technology Stack

- ⚡ [FastAPI](https://fastapi.tiangolo.com) backend with [SQLModel](https://sqlmodel.tiangolo.com) and [PostgreSQL](https://www.postgresql.org).
- 🚀 [React](https://react.dev) + TypeScript + [Vite](https://vitejs.dev) frontend, styled with [Tailwind CSS](https://tailwindcss.com) and [shadcn/ui](https://ui.shadcn.com), served by FastAPI on the same domain as the API.
- 🤖 Frontend API client generated from the backend's OpenAPI schema.
- 🔑 JWT authentication, secure password hashing, and email-based password recovery.
- ✉️ [React Email](https://react.email) templates, with [Mailpit](https://mailpit.axllent.org) for local email testing.
- 🐋 [Docker Compose](https://www.docker.com) for local services and self-hosted deployment, with [Traefik](https://traefik.io) as a reverse proxy.
- ✅ Tests with [Pytest](https://pytest.org) and [Playwright](https://playwright.dev); CI with GitHub Actions.

## Quick Start

Requirements: [Docker](https://www.docker.com), [uv](https://docs.astral.sh/uv/), and [Bun](https://bun.sh).

```bash
cp .env.example .env
docker compose run --rm backend bash scripts/prestart.sh
docker compose watch
```

Then open:

- App: <http://localhost:8000>
- API docs: <http://localhost:8000/docs>
- Mailpit: <http://localhost:8025>

The `.env` file is gitignored. Change every `changethis` value before deploying.

## Documentation

- General development (local FastAPI + Vite workflow, Docker Compose, `.env`, pre-commit): [development.md](./development.md)
- Backend: [backend/README.md](./backend/README.md)
- Frontend: [frontend/README.md](./frontend/README.md)
- Deployment to FastAPI Cloud: [deployment.md](./deployment.md)
- Self-hosted deployment with Docker Compose: [deployment-docker-compose.md](./deployment-docker-compose.md)

## License

Memorial Robot is built on the [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template), which is licensed under the terms of the MIT license. See [LICENSE](./LICENSE).
