# Code Style

Formatters and linters are the source of truth: if a tool accepts it, it's fine. Run `uv run prek run --all-files` before pushing.
The PostToolUse hook (`.claude/hooks/format.sh`) formats files after each edit.

## Python (backend/)
- Ruff format with defaults (88 cols, double quotes). Ruff lint rules: E, W, F, I, B, C4, UP, ARG001, T201. See `backend/pyproject.toml`.
- No `print` (T201). Use `logging`.
- mypy `strict = true` and `ty`: every function has full type hints, including `-> None`. Use `collections.abc.Generator` and the like, and builtin generics (`list[str]`, `X | None`).
- Models: SQLModel table and schema classes live in `app/models.py`, following the template's split: `XBase` → `XCreate` / `XUpdate` → `X(table=True)` → `XPublic` / `XsPublic`.
- DB writes that are reused go in `app/crud.py`. Simple reads can stay in the route.
- Routes (`app/api/routes/<resource>.py`):
  - `router = APIRouter(prefix="/<resource>", tags=["<resource>"])`, registered in `app/api/main.py`.
  - Inject `SessionDep` and `CurrentUser` from `app/api/deps.py`. Use `get_current_active_superuser` for admin-only routes.
  - Declare `response_model=...` and give each route a one-line docstring (it becomes the OpenAPI description).
  - Errors: `raise HTTPException(status_code=..., detail="Human readable")`. The detail strings are part of the API (tests assert on them).
- Config: add new settings to `app/core/config.py` `Settings` **and** to `.env.example`. Never read `os.environ` directly.
- Schema changes need an Alembic migration (`uv run alembic revision --autogenerate -m "..."`). Review the generated file before committing.

## TypeScript / React (frontend/)
- Biome: 2-space indentation, double quotes, no semicolons, organized imports. See `frontend/biome.json`.
- TS `strict`, with `noUnusedLocals` and `noUnusedParameters`. Avoid `any`, even though Biome allows it.
- Imports: use the `@/` alias (`@/components/...`, `@/hooks/...`) rather than deep relative paths.
- Don't hand-edit `src/client/` (generated: `bun run --filter frontend generate-client`) or `src/routeTree.gen.ts`. Leave shadcn primitives in `src/components/ui/` as generated.
- Components:
  - PascalCase files grouped by feature (`components/Items/AddItem.tsx`).
  - Arrow-function components with a default export, matching the existing code.
- Server state: TanStack Query.
  - `useSuspenseQuery` / `useQuery` for reads, keyed by resource (`["items"]`).
  - `useMutation` for writes, calling the generated `*Service`. Use `onError: handleError.bind(showErrorToast)`, and invalidate queries in `onSettled`.
- Forms: `react-hook-form` + `zod` (`zodResolver`). The schema sits above the component, with `type FormData = z.infer<typeof formSchema>`.
- User feedback goes through `useCustomToast` (`showSuccessToast` / `showErrorToast`).
- Styling: Tailwind utilities, combined with `cn()` from `@/lib/utils`. Use theme tokens (`bg-primary`, `text-muted-foreground`), not hard-coded colors.
- Use `async/await`, not `.then()` chains.
- Route pages: `head: () => ({ meta: [{ title: "<Page> - Memorial Robot" }] })`.

## General
- Name things after the domain (memories, personas, conversations), not generic `data` / `info`.
- Comments explain *why*. Don't leave commented-out code.
- No secrets in code or in `.env.example` beyond the `changethis` placeholders.
