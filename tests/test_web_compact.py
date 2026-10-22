"""Tests for the compact (max-width: 400px) media query in the served HTML pages.

Below 400px only the avatar canvas should remain, scaled to the window on a
transparent background. Every page (web/index.html and each web/avatars page)
must carry the block, positioned just before the base ``canvas`` rule so its
!important declarations win over the hard-coded 420px inline size.
"""

from __future__ import annotations

from pathlib import Path
from unittest import TestCase

WEB = Path(__file__).resolve().parents[1] / "web"

MEDIA_START = "@media (max-width: 400px)"
CANVAS_RULE = "canvas{display:block;filter:drop-shadow(0 18px 30px rgba(0,0,0,.5))}"

# The declarations that make the compact presentation work. Each must carry
# !important, because the script pins cv.style.width to 420px inline.
REQUIRED_DECLARATIONS = (
    "background:transparent !important",
    "height:96vh !important",
    "max-width:96vw !important",
    "width:auto !important",
    "filter:none !important",
    "justify-content:center !important",
    ".rig,.quip,.menu-btn,header,.dot,.rowlab{display:none !important}",
)


def _pages() -> list[Path]:
    return [WEB / "index.html", *sorted((WEB / "avatars").glob("*.html"))]


class WebCompactMediaQueryTests(TestCase):
    def test_pages_are_discovered(self) -> None:
        # The block is meant for the whole set; fail loudly if a page is missing.
        self.assertIn(WEB / "index.html", _pages())
        self.assertGreaterEqual(len(_pages()), 7)

    def test_compact_block_present_before_canvas_rule(self) -> None:
        for page in _pages():
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8")
                media_idx = text.find(MEDIA_START)
                self.assertNotEqual(media_idx, -1, f"{page.name}: media query missing")
                canvas_idx = text.find(CANVAS_RULE)
                self.assertNotEqual(
                    canvas_idx, -1, f"{page.name}: base canvas rule missing"
                )
                # The block must come before the base rule so !important wins.
                self.assertLess(media_idx, canvas_idx, f"{page.name}: wrong order")

    def test_compact_block_carries_required_declarations(self) -> None:
        for page in _pages():
            with self.subTest(page=page.name):
                text = page.read_text(encoding="utf-8")
                media_idx = text.find(MEDIA_START)
                canvas_idx = text.find(CANVAS_RULE)
                self.assertNotEqual(media_idx, -1, f"{page.name}: media query missing")
                self.assertNotEqual(canvas_idx, -1, f"{page.name}: canvas rule missing")
                # The block sits directly before the canvas rule, so this window
                # is exactly the media block.
                block = text[media_idx:canvas_idx]
                for decl in REQUIRED_DECLARATIONS:
                    self.assertIn(decl, block, f"{page.name}: missing {decl!r}")
