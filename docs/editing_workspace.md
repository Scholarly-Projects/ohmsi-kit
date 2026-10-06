# Transcript editing workspace

A local page for copy editing a generated transcript against its recording. It is built from the item-level transcript page of the [Oral History as Data template](https://github.com/uidaholib/oral-history-collections-template) and runs with Jekyll on your own computer. Nothing is published.

## Workflow

1. Process recordings in `A/` with the toolkit scripts as usual; transcripts land in `B/` with the same filename (`A/interview01.wav` → `B/interview01.csv`).
2. Copy **one** CSV from `B/` into `C/`.
3. From the toolkit root, run:

   ```bash
   bundle exec jekyll s
   ```

   The workspace opens in your browser at http://localhost:4000. It plays the recording from `A/` whose name matches the CSV.
4. Open the CSV in `C/` in VS Code (or any editor) next to the browser. Listen, correct the text, and save. The page rebuilds and reloads by itself, keeping your place in the recording.
5. When you're done, copy the corrected CSV wherever it goes next, then clear `C/` for the next transcript.

### Finding a line in the CSV

Each transcript line on the page shows a grey **L** number. That is the line number in the CSV file, so in VS Code you can press `Ctrl+G` (on Windows, Mac and Linux alike) and type the number to jump to it.

### Player controls

| Action | How |
|---|---|
| Jump to a line | Click its timestamp |
| Play / pause | `Space` (when the focus isn't on a button or field) |
| Back / forward 5 seconds | `←` / `→`, or the −5s / +5s buttons |
| Playback speed | Speed menu (remembered between reloads) |
| Keep the current line in view | "Follow playback" switch |

The line being spoken is highlighted in yellow.

### Checks and warnings

On each rebuild the workspace checks the CSV and lists problems at the top of the page (and in the terminal):

- `C/` empty, or holding more than one CSV (it then shows the most recently saved one)
- no matching recording in `A/`
- a CSV that can't be parsed, usually an unmatched double quote, with the line where parsing failed
- a file not saved as UTF-8
- missing `speaker`, `timestamp` or `words` columns
- lines with no timestamp

Individual lines are flagged in red and listed under "lines to check" when their timestamp isn't `H:MM:SS`, goes backwards, or the line has no words.

## Setup (once per computer)

Install Ruby (3.1 or newer), then from the toolkit root:

```bash
gem install bundler
bundle install
```

The page loads Bootstrap and fonts from the web, so you need an internet connection. To work offline, download Bootstrap 5's `bootstrap.min.css` and `bootstrap.bundle.min.js` into `assets/lib/` and point the two links in `_includes/head/head.html` and `_includes/foot.html` at them.

### Recording formats

MP3, M4A, WAV and FLAC all play in current Chrome, Edge, Firefox and Safari. If a recording exists in several formats, `editor: audio_preference` in `_config.yml` sets which one is used. Only the matching recording is copied into `_site/`, so a large library in `A/` doesn't slow down builds.

### Git

Add these to `.gitignore`:

```
_site/
.jekyll-cache/
.jekyll-metadata
.sass-cache/
C/*.csv
```

## How it's put together

| Piece | Role |
|---|---|
| `_plugins/editor_workspace.rb` | Finds the CSV in `C/` and the recording in `A/`, checks the CSV, and generates the page |
| `_layouts/editor.html` | The workspace page (adapted from OHD `_layouts/transcript.html`) |
| `_layouts/editor-base.html` | Minimal page shell using the OHD head and foot |
| `_includes/editor/` | Audio player, status panel, transcript lines, player script, styles |
| `_config.yml` | Folder names, live reload, and the exclude list that keeps the Python toolkit out of the build |

### Files ported from the OHD template, unchanged

```
_includes/head/head.html
_includes/foot.html
_includes/transcript/item/filters.html
_includes/transcript/item/transcript-viz.html
_includes/transcript/standardized-timestamp.html
_includes/transcript/style/filter-style.html
_includes/transcript/style/visualization-filter-legend.html
_includes/transcript/js/transcript-js.html
_sass/  (all six partials)
assets/css/cb.scss
_data/theme.yml
_data/config-theme-colors.csv
_data/filters.csv      (optional: colors the topic bar from the tags column)
```

If any of these include other OHD files, port those as well; Jekyll names the missing include when the build fails.
