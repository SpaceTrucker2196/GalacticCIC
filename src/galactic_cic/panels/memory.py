"""Memory Search Status panel for curses TUI."""

from galactic_cic import theme
from galactic_cic.panels.base import BasePanel, StyledText, Table


class MemorySearchPanel(BasePanel):
    """Panel showing memory search indexing and embedding status per agent."""

    TITLE = "Memory Search"

    def __init__(self):
        super().__init__()
        self.memory_agents = []
        self.provider = ""
        self.model = ""

    def update(self, memory_data=None):
        """Update panel data from collector."""
        if memory_data is not None:
            self.memory_agents = memory_data.get("agents", [])
            self.provider = memory_data.get("provider", "")
            self.model = memory_data.get("model", "")

    def _build_content(self):
        """Build content as StyledText for testability."""
        st = StyledText()

        if not self.memory_agents:
            st.append("  No memory search data\n", "green")
            return st

        # Provider/model header
        st.append(f"  Provider: {self.provider}  Model: {self.model}\n", "green")
        st.append("\n")

        # Per-agent table
        table = Table(
            columns=["Agent", "Indexed", "Chunks", "Vector", "Cache"],
            widths=[12, 10, 8, 8, 7],
            borders=False,
            padding=0,
        )
        for agent in self.memory_agents:
            name = agent.get("agent", "?")
            indexed = agent.get("indexed_files", 0)
            total = agent.get("total_files", 0)
            chunks = agent.get("chunks", 0)
            vector = agent.get("vector", "?")
            cache = agent.get("cache_entries", 0)
            dirty = agent.get("dirty", False)
            embeddings = agent.get("embeddings", "")

            # Indexed column
            if embeddings == "unavailable":
                idx_str = f"✖ {indexed}/{total}"
                style = "red"
            elif total == 0:
                idx_str = "0/0"
                style = "green"
            elif indexed == total and not dirty:
                idx_str = f"● {indexed}/{total}"
                style = "green"
            elif dirty or indexed < total:
                idx_str = f"◐ {indexed}/{total}"
                style = "yellow"
            else:
                idx_str = f"○ {indexed}/{total}"
                style = "green"

            # Vector status
            if vector == "ready":
                vec_str = "● ready"
            elif embeddings == "unavailable":
                vec_str = "✖ nokey"
            else:
                vec_str = f"○ {vector}"

            cache_str = str(cache) if cache > 0 else "—"

            table.add_row([name, idx_str, str(chunks), vec_str, cache_str], style=style)

        table_st = table.render()
        offset = len(st._text)
        st._text += table_st._text
        for span in table_st._spans:
            st._spans.append(StyledText.Span(
                span.start + offset, span.end + offset, span.style
            ))

        # Totals
        total_indexed = sum(a.get("indexed_files", 0) for a in self.memory_agents)
        total_files = sum(a.get("total_files", 0) for a in self.memory_agents)
        total_chunks = sum(a.get("chunks", 0) for a in self.memory_agents)
        total_cache = sum(a.get("cache_entries", 0) for a in self.memory_agents)

        st.append(f"\n  Total: {total_indexed}/{total_files} files, "
                   f"{total_chunks} chunks, {total_cache} cached\n", "green")

        return st

    def _draw_content(self, win, y, x, height, width):
        """Render memory search content into curses window."""
        row = 0

        if not self.memory_agents:
            self._safe_addstr(win, y, x, "  No memory search data", self.c_dim, width)
            return

        # Provider/model header
        line = f" Provider: {self.provider}  Model: {self.model}"
        self._safe_addstr(win, y + row, x, line, self.c_normal, width)
        row += 1

        if row >= height:
            return

        # Per-agent table
        table = Table(
            columns=["Agent", "Indexed", "Chunks", "Vector", "Cache"],
            widths=[12, 10, 8, 8, 7],
            borders=False,
            padding=0,
        )

        any_errors = False
        for agent in self.memory_agents:
            name = agent.get("agent", "?")
            indexed = agent.get("indexed_files", 0)
            total = agent.get("total_files", 0)
            chunks = agent.get("chunks", 0)
            vector = agent.get("vector", "?")
            cache = agent.get("cache_entries", 0)
            dirty = agent.get("dirty", False)
            embeddings = agent.get("embeddings", "")

            if embeddings == "unavailable":
                idx_str = f"✖ {indexed}/{total}"
                style = "red"
                any_errors = True
            elif total == 0:
                idx_str = "0/0"
                style = "green"
            elif indexed == total and not dirty:
                idx_str = f"● {indexed}/{total}"
                style = "green"
            elif dirty or indexed < total:
                idx_str = f"◐ {indexed}/{total}"
                style = "yellow"
            else:
                idx_str = f"○ {indexed}/{total}"
                style = "green"

            if vector == "ready":
                vec_str = "● ready"
            elif embeddings == "unavailable":
                vec_str = "✖ nokey"
            else:
                vec_str = f"○ {vector}"

            cache_str = str(cache) if cache > 0 else "—"
            table.add_row([name, idx_str, str(chunks), vec_str, cache_str], style=style)

        rows_drawn = table.draw(win, y + row, x, width,
                                self.c_normal, self.c_error, self.c_warn)
        row += rows_drawn

        # Totals
        if row < height:
            total_indexed = sum(a.get("indexed_files", 0) for a in self.memory_agents)
            total_files = sum(a.get("total_files", 0) for a in self.memory_agents)
            total_chunks = sum(a.get("chunks", 0) for a in self.memory_agents)
            total_cache = sum(a.get("cache_entries", 0) for a in self.memory_agents)

            row += 1
            if row < height:
                line = f" Total: {total_indexed}/{total_files} files, {total_chunks} chunks, {total_cache} cached"
                self._safe_addstr(win, y + row, x, line, self.c_dim, width)

    def _draw_detail(self, win, y, x, height, width):
        """Full-screen detail view for Memory Search."""
        row = 0

        self._safe_addstr(win, y + row, x, "  MEMORY SEARCH — Detail View",
                          self.c_highlight, width)
        row += 2

        # Provider info
        self._safe_addstr(win, y + row, x, "  Configuration",
                          self.c_table_heading, width)
        row += 1
        self._safe_addstr(win, y + row, x, f"    Provider:   {self.provider}",
                          self.c_normal, width)
        row += 1
        self._safe_addstr(win, y + row, x, f"    Model:      {self.model}",
                          self.c_normal, width)
        row += 2

        # Per-agent detail
        self._safe_addstr(win, y + row, x, "  Per-Agent Status",
                          self.c_table_heading, width)
        row += 1

        for agent in self.memory_agents:
            if row + 8 >= height:
                break

            name = agent.get("agent", "?")
            indexed = agent.get("indexed_files", 0)
            total = agent.get("total_files", 0)
            chunks = agent.get("chunks", 0)
            dirty = agent.get("dirty", False)
            vector = agent.get("vector", "?")
            fts = agent.get("fts", "?")
            cache_enabled = agent.get("cache_enabled", False)
            cache_entries = agent.get("cache_entries", 0)
            store = agent.get("store", "?")
            sources = agent.get("sources", "?")
            embeddings = agent.get("embeddings", "")
            embeddings_error = agent.get("embeddings_error", "")

            # Status icon
            if embeddings == "unavailable":
                icon, attr = "✖", self.c_error
            elif indexed == total and total > 0 and not dirty:
                icon, attr = "●", self.c_normal
            elif dirty or indexed < total:
                icon, attr = "◐", self.c_warn
            else:
                icon, attr = "○", self.c_dim

            self._safe_addstr(win, y + row, x, f"    {icon} {name}", attr, width)
            row += 1

            details = [
                ("Files", f"{indexed}/{total} indexed"),
                ("Chunks", str(chunks)),
                ("Dirty", "yes" if dirty else "no"),
                ("Vector", vector),
                ("FTS", fts),
                ("Cache", f"{'enabled' if cache_enabled else 'disabled'} ({cache_entries} entries)"),
                ("Sources", sources),
                ("Store", store),
            ]
            if embeddings and embeddings != "unknown":
                details.append(("Embeddings", embeddings))
            if embeddings_error:
                details.append(("Error", embeddings_error))

            for label, val in details:
                if row >= height:
                    break
                lattr = self.c_error if label == "Error" else self.c_dim
                self._safe_addstr(win, y + row, x,
                                  f"      {label + ':':<12} {val}", lattr, width)
                row += 1
            row += 1

        # Summary
        if row + 3 < height:
            self._safe_addstr(win, y + row, x, "  Summary",
                              self.c_table_heading, width)
            row += 1
            total_indexed = sum(a.get("indexed_files", 0) for a in self.memory_agents)
            total_files = sum(a.get("total_files", 0) for a in self.memory_agents)
            total_chunks = sum(a.get("chunks", 0) for a in self.memory_agents)
            total_cache = sum(a.get("cache_entries", 0) for a in self.memory_agents)
            self._safe_addstr(win, y + row, x,
                              f"    Files:    {total_indexed}/{total_files}",
                              self.c_normal, width)
            row += 1
            self._safe_addstr(win, y + row, x,
                              f"    Chunks:   {total_chunks}",
                              self.c_normal, width)
            row += 1
            self._safe_addstr(win, y + row, x,
                              f"    Cached:   {total_cache} embeddings",
                              self.c_normal, width)
