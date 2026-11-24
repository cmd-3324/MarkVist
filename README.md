# markvist

A tiny Markdown viewer and editor for people who do not want to open a whole IDE
to read a `.md` file.

One window, a few files in tabs, no workspace, no extensions, no language
servers. It is a Python + Tkinter application with no third-party dependencies,
so it starts instantly and sits around 30 MB of RAM instead of the several
hundred an editor platform needs.

## Features

- **Tabs for up to 10 files** — open several `.md` files and switch between them;
  each tab keeps its own text and unsaved-changes dot (`Ctrl+Tab`, `Ctrl+W`).
- **Restores your last session** — the tabs you had open come back on the next
  launch, with the same one active. Untitled buffers are not restored.
- **Find and replace** — `Ctrl+F` searches the source and the rendered preview
  together, highlights every hit in **both** panes, counts each occurrence once
  even though it appears twice on screen, and steps through them with `F3` /
  `Shift+F3` and an `n of m` counter; `Ctrl+H` adds replace and replace-all,
  with case and whole-word toggles.
- **Unsaved notes survive a restart** — untitled tabs are shadowed to disk as
  you type and reopened (still unsaved, still marked with a dot) on the next
  launch, even after a crash.
- **Editing tools** — undo/redo, cut/copy/paste, go to line (`Ctrl+G`), word-wrap
  toggle and an *Open recent* menu.
- **New file, open file, open folder** — `Ctrl+N`, `Ctrl+O` (multi-select), and
  `Ctrl+Shift+O` to load every Markdown file in a folder at once, sorted by
  name, with no file-list dialog in between.
- **Start screen** — launched with no arguments, the window offers New / Open /
  Open folder plus your recent files instead of an empty editor.
- **One view switch** with three positions: book (rendered), split, code (source).
- **Editable and read-only** — Read mode disables typing entirely.
- **Zoom** with `Ctrl+=` / `Ctrl+-`, `Ctrl+0` to reset, 60 %–240 %, remembered.
- **Themes** — light and dark, `Ctrl+T`, remembered.
- **Auto save** — on by default, writes 900 ms after you stop typing (toggle in
  the View menu; untitled files still ask where to save).
- **No silent overwrites** — when a file changed on disk since markvist read it,
  auto save pauses and the tab shows `⚠`; saving then offers *Reload from disk*,
  *Keep mine* (the replaced file is copied to `name.md.bak`) or *Save a copy*.
  `F5` reloads any tab on demand.
- **Fonts** — separate reading font for the document and monospace font for the
  source pane; the app chrome is never restyled.
- **Modern document rendering** — a real type scale with rules under H1/H2,
  bold/italic/strikethrough, tinted inline code, clickable links, image
  placeholders, checkboxes for task lists, banded blockquotes with an accent
  bar, code cards with a language caption, and tables drawn as actual grids
  with header shading, zebra rows and per-column alignment.
- **Standalone `markvist.exe`** — a single-file Windows build, no Python needed
  (see below).
- **RTL support** — Persian, Arabic and Hebrew are detected automatically, with a
  visual-order preview for Tk builds that predate bidirectional text.
- **CLI friendly** — `markvist notes.md`.

## Requirements

- Python 3.10 or newer with Tkinter (included in the python.org Windows
  installer and most Linux distributions' `python3-tk` package).
- Tk 9.1+ for native right-to-left text; Tk 8.6/9.0 works with the visual-order
  preview described below.

## Install and run

From a clone, without installing anything:

```bash
python -m pip install -e .   # optional, gives you the `markvist` command
markvist                     # or: python -m markvist
```

On Windows you can also double-click `markvist.bat`, which puts `src/` on the
path and launches the app with `pythonw` (no console window), or run the
prebuilt `dist\markvist.exe` described below. To make `.md`
files open in markvist, use *Open with → Choose another app → Look for another
app* and pick `markvist.bat`.

## Standalone executable (Windows)

`build_exe.bat` packages the app into one self-contained file with PyInstaller:

```bat
python -m pip install pyinstaller
build_exe.bat
```

The result is `dist\markvist.exe` — a single file with Python and Tk inside
(around 12 MB). It needs no Python install, keeps the same config in
`%APPDATA%\markvist`, and accepts files on the command line, so you can use it
as an *Open with* target for `.md` files.

Rebuild it after changing the source; `build/`, `dist/` and the generated
`markvist.spec` are ignored by git.

## Keyboard shortcuts

| Action | Shortcut |
| --- | --- |
| New file | `Ctrl+N` |
| Open file(s) | `Ctrl+O` |
| Open a folder of `.md` files | `Ctrl+Shift+O` |
| Save | `Ctrl+S` |
| Save as | `Ctrl+Shift+S` |
| Close tab | `Ctrl+W` |
| Next tab | `Ctrl+Tab` |
| Find in source and preview | `Ctrl+F` |
| Find and replace | `Ctrl+H` |
| Next / previous match | `F3` / `Shift+F3` |
| Go to line | `Ctrl+G` |
| Scroll the rendered view | `↑` `↓` `PgUp` `PgDn` `Home` `End` |
| Zoom in / out | `Ctrl+=` / `Ctrl+-` |
| Reset zoom | `Ctrl+0` |
| Cycle book / split / code | `Ctrl+E` |
| Switch theme | `Ctrl+T` |

The View menu holds auto save, word wrap, the two font pickers, text direction
and the visual RTL preview toggle.

### Find and replace

The find bar searches **both** panes but counts **occurrences**, not highlights:
the same word in the source and in the rendered text is one entry in the
`n of m` counter, highlighted in both places at once. Text that only exists in
one pane (a link target in the source, a bullet glyph in the preview) counts
once and is highlighted where it lives.

Replacement always edits the **source** — that is the file — and after a
*Replace all* the preview is re-rendered before the counter and the “Replaced N
occurrences” message are updated, so both agree. If the current occurrence
only exists in the preview, *Replace* says so. Replacing is refused in Read
mode, where the source is not editable.

### Unsaved notes

An untitled tab has no file to save to, so its text is written to
`%APPDATA%\markvist\shadows.json` about a second after you stop typing, and on
exit. It is reopened on the next launch as a dirty untitled tab, so a crash or
a closed window does not lose it. Saving the note to a real file, closing the
tab, or answering “No” to the unsaved-changes prompt at exit removes its shadow.

### Files changed by other programs

Each tab remembers the file's size and modification time as it was read or
written. Before any write it compares them again; if they differ, the write
stops and you choose:

- **Reload from disk** — the tab takes the file's version and your edits in that
  tab are dropped.
- **Keep mine** — the tab is written over the file, and the version being
  replaced is copied first to `name.md.bak` next to it.
- **Save a copy…** — the tab is written to a file you pick and the changed file
  is left untouched.

Auto save never opens a dialog from its timer: it just pauses, marks the tab
with `⚠`, and says so in the status bar. `Ctrl+S` then asks. Selecting
anything, cancelling the dialog, or closing it leaves the file alone.

## Right-to-left text (Persian, Arabic, Hebrew)

The app detects an RTL document and lays it out right to left: paragraphs and
headings are right-aligned, list markers move to the right, and the quote bar
moves with them.

**Bidirectional text is a Tk feature, not an app feature.** Tk gained native
bidi support in **9.1** (September 2026). On 8.6/9.0 — including the Tk 9.0 that
current CPython installers bundle — the text widget draws characters in logical
order, so a Persian word appears with its letters reversed.

For that case the app offers **View → Visual RTL preview** (on by default): each
RTL run is reversed into visual order before it is drawn, so the preview reads
correctly. The status badge says `RTL · preview visual order` so it never claims
more than it does, and `Help → About RTL support` explains the situation for the
Tk build you are running.

Limits of the visual preview:

- Copying text from the preview returns reversed characters.
- The source pane always shows the file's logical order — it is the file.
- It is a simplified run-based algorithm, not the full Unicode bidi algorithm, so
  deeply nested mixed-direction text can still be off.

When Tk 9.1 is available the app notices, turns the workaround off, and the
badge simply reads `RTL`.

## Project layout

```
markvist/
├── src/markvist/
│   ├── __init__.py      version
│   ├── __main__.py      python -m markvist
│   ├── app.py           window, toolbar, menus, file handling
│   ├── bidi.py          visual-order reordering for RTL previews
│   ├── document.py      one open document (one tab)
│   ├── markdown.py      parser: Markdown -> block structures
│   ├── prefs.py         JSON config in %APPDATA%/markvist
│   ├── render.py        block structures -> styled Tk text
│   ├── theme.py         palettes, sizes, font choices
│   └── widgets.py       the three-position view switch
├── tests/               unittest suite (no display required)
├── pyproject.toml
├── build_exe.bat        PyInstaller one-file build
├── exe_entry.py         entry script used by the build
├── markvist.bat         Windows launcher (needs Python)
└── README.md
```

## Development

```bash
python -m unittest discover -s tests -v
```

The tests only import `markvist.markdown` and `markvist.bidi`, so they run
headless. CI runs them on Ubuntu and Windows for Python 3.10 and 3.13.

## Known limitations

- At most 10 files open at once. Opening a folder with more Markdown files
  loads the first 10 and says so in the status bar; no dialog interrupts you.
- "Open folder" lists the `.md` files directly inside the chosen folder, not
  subfolders.
- No drag and drop (Tk needs a third-party package for it).
- No syntax highlighting inside fenced code blocks; the language name is
  shown above the block.
- Images are not decoded: a block shows the accent placeholder with the alt
  text and stays clickable.
- Tables use their natural width and scroll with the text; a table wider than
  the preview pane is clipped rather than squeezed into columns.
- Shadow copies hold untitled notes only; saved files rely on the file itself
  and on auto save.
- Outside changes are caught when markvist is about to write, not by a file
  watcher: a tab with no unsaved edits keeps showing what it loaded until you
  reload it with `F5` (or save over it, which asks first).
- The find bar has no regular-expression mode; it matches plain text with
  optional case and whole-word sensitivity.

## License

No license file yet — add one before publishing if you want others to reuse it.
