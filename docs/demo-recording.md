# Recording a Demo GIF

A 20–30 second GIF in the README is worth more than a live deployment. Recruiters scan GitHub repos for under 60 seconds — a demo GIF lets them see the system working without cloning anything.

## Demo Flow

Record this exact sequence:

1. **Open the dashboard** at `http://localhost:5173`
2. **Send a notification** from the Playground tab
3. **Enable provider failure** using the toggle
4. **Send another notification** — it fails and moves to the DLQ
5. **Switch to the DLQ tab** — see the failed message
6. **Disable failure, click Retry** — message delivers successfully

Total time: ~20 seconds.

## Setup Before Recording

```bash
# Start the full stack
make run-demo

# Wait for the dashboard to open at http://localhost:5173
# Navigate to the Playground tab
```

## Recording Tools

### Option 1: Kap (macOS, free, open source)

Best for: Quick screen recordings with GIF export.

```bash
brew install --cask kap
```

1. Open Kap from the menu bar
2. Select the browser window area (crop to the dashboard)
3. Click Record
4. Walk through the demo flow above
5. Stop recording → Export as GIF
6. Set quality to "Medium" and FPS to 15 (keeps file size under 5MB)
7. Save to `docs/demo.gif`

### Option 2: Screen Studio (macOS, paid)

Best for: Polished recordings with automatic zoom effects.

1. Open Screen Studio
2. Select the browser window
3. Record the demo flow
4. Use auto-zoom on click areas (makes it easier to see interactions)
5. Export as GIF at 720p, 15fps
6. Save to `docs/demo.gif`

### Option 3: Peek (Linux, free)

```bash
# Ubuntu/Debian
sudo apt install peek

# Fedora
sudo dnf install peek
```

1. Open Peek, position the frame over the dashboard
2. Click Record
3. Walk through the demo flow
4. Stop → saves as GIF automatically
5. Move to `docs/demo.gif`

### Option 4: Charm VHS (Terminal GIF)

For a terminal-only recording showing curl commands and responses:

```bash
brew install charmbracelet/tap/vhs
vhs docs/demo.tape
# Outputs: docs/demo.gif
```

### Option 5: gifcap.dev (Browser-based, no install)

1. Go to [gifcap.dev](https://gifcap.dev)
2. Click "Start Recording" and select the browser tab
3. Walk through the demo flow
4. Click "Stop" → renders a GIF in the browser
5. Download and save as `docs/demo.gif`

## Tips for a Good Recording

- **Resize the browser** to ~1200x700 before recording — oversized windows produce blurry GIFs
- **Use the Playground tab** — it has the send form, failure toggle, and activity log all in one view
- **Pause briefly** after each action so viewers can read the response
- **Keep it under 30 seconds** and under 5MB — GitHub renders GIFs inline but large files load slowly
- **15fps is enough** — smoother looks better but doubles file size for minimal benefit

## Adding the GIF to README

Once you have `docs/demo.gif`, the README already references it:

```markdown
![Notifii Demo](docs/demo.gif)
```

Commit and push:

```bash
git add docs/demo.gif
git commit -m "docs: add demo GIF"
git push
```

The GIF will render inline on the GitHub repo page.
