# Test execution setup (no environment variables needed)

Open **Feature Testing -> Setup & supervisor**. The page shows a checklist; fix each red item.

1. **Turn on test execution** - generates the operator and supervisor tokens for you.
2. **Pick the XiHeadless checkout** - the page lists checkouts found next to the Toolkit (set
   `MISSION_TOOLKIT_TEST_SEARCH_ROOTS` to add folders). It must be built (`bin/mcp/XiHeadless.dll`).
3. **Enter the disposable test character ID** (never a real character).
4. **Read-only database login** - run the two SQL lines shown on the page in your MariaDB console, then enter
   that user, password and database name. Without it a run is reported BLOCKED, not PASS/FAIL.
5. **Save**, then open **Build & run**, enter account + character, tick the approval box, launch and confirm.
   No token is pasted when setup is turned on.

Settings are stored in `data/test_execution/settings.json` (git-ignored; contains tokens and the DB password).
Real environment variables, if set, override the file. Restart the Toolkit after changing the DB login or after
turning execution on for the first time so the supervisor process picks up its token.

Security note: UI mode accepts launches only from loopback, same-origin browser requests carrying the
`X-Requested-With: toolkit-ui` header. It protects against other websites and API/model tools, not against
local programs that can read the settings file.
