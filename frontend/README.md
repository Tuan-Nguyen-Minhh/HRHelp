# HR Help frontend

This is a dependency free frontend for the currently implemented FastAPI flow.

1. Run the database and API as described in the repository setup. The API listens on `http://localhost:8000`.
2. From this directory run `python3 -m http.server 3000`.
3. Open `http://localhost:3000`.

The frontend uses `/api/v1` on `http://localhost:8000` by default. To target a different API, set `window.HR_HELP_API_BASE` to its origin before `app.js` loads. The API must allow that frontend origin in `CORS_ORIGINS`.

Registration, login, case creation, chat, fact confirmation, and reading an answer are wired to the API. The backend does not yet expose a case list, message history, draft reader, legal review, or issued decision endpoint, so those actions are not presented as available. A case can be reopened by its ID during the browser session or by pasting its URL after signing in.
