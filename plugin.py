import gradio as gr

from shared.utils.plugins import WAN2GPPlugin

from . import cleaner
from . import settings


def _log(message):
    print(f"[Gradio Cache Cleaner] {message}")


_scheduler = cleaner.Scheduler(settings.get, _log)


class GradioCacheCleanerPlugin(WAN2GPPlugin):
    def __init__(self):
        super().__init__()
        self.name = "Gradio Cache Cleaner"
        self.version = "0.1"
        self.description = "Deletes old copies from Gradio's cache folder, which otherwise keeps every video you view or upload."
        settings.load()

    def setup_ui(self):
        self.add_tab(tab_id="gradio_cache_cleaner", label="Gradio Cache", component_constructor=self.create_ui)
        _scheduler.start()

    # ------------------------------------------------------------------ UI
    @staticmethod
    def _status():
        folder = cleaner.cache_folder()
        problem = cleaner.unsafe_reason(folder)
        if problem and "doesn't exist" not in problem:
            return f"**Cache folder:** `{folder}`\n\n⚠️ Not cleaned: {problem}. Check the GRADIO_TEMP_DIR setting of your launcher."
        count, size = cleaner.folder_stats(folder) if not problem else (0, 0)
        return f"**Cache folder:** `{folder}`\n\n**Now:** {count} file(s), {cleaner.human_size(size)}"

    def create_ui(self):
        current = settings.get()
        gr.Markdown(
            "## Gradio Cache Cleaner\n"
            "Gradio copies every file it shows (each generated video in the gallery, previews) and every file you upload "
            "into its cache folder, and never deletes them. This deletes old copies. Your outputs are never touched.\n\n"
            "Deleting a copy that is still on screen stops it playing until you reload the page; a queued task that uses "
            "an uploaded file needs that file, so keep the age longer than your longest queue."
        )
        status = gr.Markdown(self._status())
        enabled = gr.Checkbox(value=current["enabled"], label="Clean automatically")
        with gr.Row():
            age = gr.Slider(1, 168, step=1, value=current["max_age_hours"], label="Delete cached files older than (hours)")
            every = gr.Slider(5, 240, step=5, value=current["check_minutes"], label="Check every (minutes)")
        previous = gr.Checkbox(value=current["clear_previous_runs"],
                               label="At start-up, delete everything left by earlier runs")
        with gr.Row():
            refresh = gr.Button("Refresh")
            clean_old = gr.Button("Delete files older than the set age")
            clean_previous = gr.Button("Delete files from earlier runs")
            clean_all = gr.Button("Delete everything", variant="stop")
        result = gr.Markdown()

        def save(key):
            def handler(value):
                settings.set_value(key, value)
                _scheduler.settings_changed()
            return handler

        enabled.change(save("enabled"), inputs=enabled, show_progress="hidden")
        age.release(save("max_age_hours"), inputs=age, show_progress="hidden")
        every.release(save("check_minutes"), inputs=every, show_progress="hidden")
        previous.change(save("clear_previous_runs"), inputs=previous, show_progress="hidden")

        def run(label, **kwargs):
            def handler():
                text = cleaner.describe(cleaner.sweep(**kwargs), label)
                _log(text)
                return text, self._status()
            return handler

        refresh.click(self._status, outputs=status)
        clean_old.click(lambda: run("Clean", max_age=settings.get()["max_age_hours"] * 3600)(), outputs=[result, status])
        clean_previous.click(run("Earlier runs", created_before=cleaner.RUN_STARTED), outputs=[result, status])
        clean_all.click(run("Everything", max_age=-1), outputs=[result, status])
