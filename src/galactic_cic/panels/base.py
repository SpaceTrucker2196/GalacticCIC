"""Base panel class with box-drawing for curses TUI."""

import curses

from galactic_cic import theme


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


class Table:
    """Simple table layout for curses panels.

    Usage:
        table = Table(["Name", "Status", "Tokens"], widths=[14, 8, 10])
        table.add_row(["main*", "online", "126k"])
        table.add_row(["rentalops", "online", "65k"], style="green")
        table.add_row(["raven", "error", "0k"], style="red")

        # Render to StyledText
        st = table.render()

        # Or draw directly to curses window
        table.draw(win, y, x, width, color_normal, color_error, color_warn)
    """

    HSEP = "─"
    VSEP = "│"
    TL = "┌"
    TR = "┐"
    BL = "└"
    BR = "┘"
    TJ = "┬"  # top junction
    BJ = "┴"  # bottom junction
    LJ = "├"  # left junction
    RJ = "┤"  # right junction
    CJ = "┼"  # cross junction

    def __init__(self, columns, widths=None, padding=1, borders=True, header=True):
        """
        Args:
            columns: list of column header strings
            widths: list of column widths (auto-calculated if None)
            padding: spaces on each side of cell content
            borders: draw box borders between columns
            header: show header row with separator
        """
        self.columns = columns
        self.padding = padding
        self.borders = borders
        self.show_header = header
        self.rows = []
        self.row_styles = []

        if widths:
            self.widths = widths
        else:
            self.widths = [max(len(c) + 2, 6) for c in columns]

    def add_row(self, values, style="green"):
        """Add a row of values with optional style (green/red/yellow)."""
        # Pad or truncate to match column count
        row = list(values) + [""] * (len(self.columns) - len(values))
        self.rows.append(row[:len(self.columns)])
        self.row_styles.append(style)

    def _format_cell(self, text, width):
        """Format a cell value to fit the given width."""
        text = str(text)
        pad = " " * self.padding
        inner_width = width - (self.padding * 2)
        if len(text) > inner_width:
            text = text[:inner_width - 1] + "…"
        return pad + text.ljust(inner_width) + pad

    def _make_separator(self, left, mid, right, fill):
        """Build a horizontal separator line."""
        parts = []
        for i, w in enumerate(self.widths):
            parts.append(fill * w)
        if self.borders:
            return left + mid.join(parts) + right
        else:
            return fill.join(parts)

    def render(self):
        """Render table to a StyledText object."""
        st = StyledText()

        if self.show_header:
            # Header row — uses table_heading style (grey)
            header_cells = []
            for i, col in enumerate(self.columns):
                header_cells.append(self._format_cell(col, self.widths[i]))
            if self.borders:
                line = self.VSEP + self.VSEP.join(header_cells) + self.VSEP
            else:
                line = " ".join(header_cells)
            st.append(line + "\n", "table_heading")

            # Header separator
            sep = self._make_separator(
                self.LJ if self.borders else "",
                self.CJ if self.borders else self.HSEP,
                self.RJ if self.borders else "",
                self.HSEP,
            )
            st.append(sep + "\n", "table_heading")

        # Data rows
        for row_idx, row in enumerate(self.rows):
            style = self.row_styles[row_idx] if row_idx < len(self.row_styles) else "green"
            cells = []
            for i, val in enumerate(row):
                cells.append(self._format_cell(val, self.widths[i]))
            if self.borders:
                line = self.VSEP + self.VSEP.join(cells) + self.VSEP
            else:
                line = " ".join(cells)
            st.append(line + "\n", style)

        return st

    def draw(self, win, y, x, max_width, c_normal, c_error=None, c_warn=None):
        """Draw table directly to a curses window.

        Args:
            win: curses window
            y: start row
            x: start column
            max_width: max width to draw
            c_normal: normal (green) color attribute
            c_error: error (red) color attribute
            c_warn: warning (yellow) color attribute
        Returns:
            Number of rows drawn
        """
        c_error = c_error or c_normal
        c_warn = c_warn or c_normal
        row_num = 0

        # Grey heading color from theme system
        c_heading = theme.get_attr(theme.TABLE_HEADING)

        style_map = {
            "green": c_normal,
            "red": c_error,
            "yellow": c_warn,
            "warn": c_warn,
            "error": c_error,
        }

        if self.show_header:
            # Header — grey color from theme
            header_cells = []
            for i, col in enumerate(self.columns):
                header_cells.append(self._format_cell(col, self.widths[i]))
            if self.borders:
                line = self.VSEP + self.VSEP.join(header_cells) + self.VSEP
            else:
                line = " ".join(header_cells)
            try:
                win.addnstr(y + row_num, x, line, max_width, c_heading)
            except curses.error:
                pass
            row_num += 1

            # Separator
            sep = self._make_separator(
                self.LJ if self.borders else "",
                self.CJ if self.borders else self.HSEP,
                self.RJ if self.borders else "",
                self.HSEP,
            )
            try:
                win.addnstr(y + row_num, x, sep, max_width, c_heading)
            except curses.error:
                pass
            row_num += 1

        # Data rows
        for row_idx, row in enumerate(self.rows):
            style = self.row_styles[row_idx] if row_idx < len(self.row_styles) else "green"
            attr = style_map.get(style, c_normal)
            cells = []
            for i, val in enumerate(row):
                cells.append(self._format_cell(val, self.widths[i]))
            if self.borders:
                line = self.VSEP + self.VSEP.join(cells) + self.VSEP
            else:
                line = " ".join(cells)
            try:
                win.addnstr(y + row_num, x, line, max_width, attr)
            except curses.error:
                pass
            row_num += 1

        return row_num


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
        self.c_table_heading = theme.get_attr(theme.TABLE_HEADING)

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
