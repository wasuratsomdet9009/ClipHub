"""Feature pages in sidebar order: (Thai label, icon key, page class).

Each page emits task_submitted(BaseMediaTask); MainWindow connects it to TaskQueue.enqueue.
"""
from __future__ import annotations

from ui.pages.compressor_page import CompressorPage
from ui.pages.converter_page import ConverterPage
from ui.pages.downloader_page import DownloaderPage
from ui.pages.subtitle_page import SubtitlePage

PAGES = [
    ("ดาวน์โหลด", "download", DownloaderPage),
    ("แปลงไฟล์", "convert", ConverterPage),
    ("บีบอัด", "compress", CompressorPage),
    ("ซับไตเติล", "subtitle", SubtitlePage),
]
