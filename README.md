# Gradio Cache Cleaner for Wan2GP

Gradio, the web interface Wan2GP runs on, copies every file it shows (each generated video in the gallery,
previews) and every file you upload into its cache folder, and never deletes them. With large videos that folder
can grow by tens of GB a day. This plugin deletes old copies. Your outputs are never touched.

## Features

- Deletes cached files older than a set age (12 hours by default), checked every 30 minutes.
- At start-up, deletes everything left by earlier runs.
- **Gradio Cache** tab: folder size, settings, and buttons to clean now.
- Works with any install (standalone, Pinokio, StabilityMatrix...): it cleans the folder Gradio itself uses,
  `GRADIO_TEMP_DIR` when set, otherwise `<system temp>/gradio`.

A deleted copy that is still on screen stops playing until you reload the page. Queued tasks that use an uploaded
file need that file, so keep the age longer than your longest queue.

## Install

In Wan2GP, open the **Plugins** tab, paste this repository's URL under *Install New Plugin*, install,
enable it and restart Wan2GP.

## License

MIT
