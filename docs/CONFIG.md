Configuration

Environment variables
- `PLEX_BASE_URL` — Base URL of your Plex server (e.g., `http://192.168.1.10:32400`).
- `PLEX_TOKEN` — Your Plex token.

Setup
- Copy `example.env` to `.env` and fill in values. The UI and CLI will read it automatically via `python-dotenv`.

Streamlit settings (optional)
- Create `.streamlit/config.toml` to tweak limits, for example:
```
[server]
maxMessageSize = 250
headless = true

[browser]
gatherUsageStats = false
```
Raising `maxMessageSize` is rarely needed since the app pages results, but can help with very large rows or thumbnails.

Rate limiting and retries
- The CLI supports `--sleep` and `--max-per-minute` to avoid overwhelming Plex.
- The UI’s batch updater applies a per-item sleep derived from the max-per-minute value. Individual requests retry with exponential backoff.

Unraid and Windows notes
- Unraid: Run the Python app in a container or your server’s Python. Mount a `.env` file with your token.
- Windows: Use PowerShell wrapper `scripts/run-cli.ps1`, or run `python src/cli.py ...` directly in a venv.

