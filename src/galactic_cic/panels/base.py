"""Base panel class with box-drawing for curses TUI."""

import curses


class StyledText:
    """Lightweight text container compatible with test assertions.

    Mimics the subset of rich.text.Text used by step definitions:
      - .plain  -> raw string content
      - ._spans -> list of Span(start, end, style) for color checks
    """

    class Span:
        def __init__(self, start, end, style):
            self.start = start
            self.end = end
            self.style = style

        def __repr__(self):
            return f"Span({self.start}, {self.end}, {self.style!r})"

    def __init__(self, text=""):
        self._text = text
        self._spans = []

    @property
    def plain(self):
        return self._text

    def append(self, text, style=""):
        start = len(self._text)
        self._text += text
        if style:
            self._spans.append(self.Span(start, len(self._text), style))
        return self

    def __str__(self):
        return self._text


class BasePanel:
    """Base class for dashboard panels with box-drawing rendering."""

    TITLE = ""

    # Box-drawing characters
    TL = "\u250c"  # ┌
    TR = "\u2510"  # ┐
    BL = "\u2514"  # └
    BR = "\u2518"  # ┘
    H = "\u2500"   # ─
    V = "\u2502"   # │

    def __init__(self):
        self.focused = False
        self.lines = []

    def draw(self, win, y, x, height, width, color_normal, color_highlight,
             color_warn, color_error, color_dim):
        """Draw the panel with box border and content into a curses window."""
        if height < 3 or width < 4:
            return

        # Store color pairs for subclasses
        self.c_normal = color_normal
        self.c_highlight = color_highlight
        self.c_warn = color_warn
        self.c_error = color_error
        self.c_dim = color_dim

        border_color = color_highlight if self.focused else color_normal

        # Top border with title
        title = f" {self.TITLE} "
        top_line = self.TL + self.H + title
        remaining = width - len(top_line) - 1
        if remaining > 0:
            top_line += self.H * remaining
        top_line += self.TR
        try:
            win.addnstr(y, x, top_line, width, border_color)
        except curses.error:
            pass

        # Side borders and content area
        content_h = height - 2
        for row in range(content_h):
            try:
                win.addstr(y + 1 + row, x, self.V, border_color)
                win.addstr(y + 1 + row, x + width - 1, self.V, border_color)
                # Clear content area
                inner = " " * (width - 2)
                win.addnstr(y + 1 + row, x + 1, inner, width - 2, color_normal)
            except curses.error:
                pass

        # Bottom border
        bot_line = self.BL + self.H * (width - 2) + self.BR
        try:
            win.addnstr(y + height - 1, x, bot_line, width, border_color)
        except curses.error:
            pass

        # Draw content lines
        self._draw_content(win, y + 1, x + 1, content_h, width - 2)

    def _draw_content(self, win, y, x, height, width):
        """Override in subclasses to draw panel-specific content."""
        pass

    def _safe_addstr(self, win, y, x, text, attr, max_width=None):
        """Safely add a string to window, handling boundary errors."""
        try:
            if max_width:
                win.addnstr(y, x, text, max_width, attr)
            else:
                win.addstr(y, x, text, attr)
        except curses.error:
            pass
