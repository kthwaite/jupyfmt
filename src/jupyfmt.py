import json
import re
from abc import ABC, abstractmethod

import psutil
from black import FileMode, format_cell
from black.report import NothingChanged
from IPython.display import Javascript, display


class BaseBlackFormatter(ABC):
    def __init__(self, ip):
        self.ip = ip

    @abstractmethod
    def _set_cell(self, cell_id: int, raw_cell: str, fmt_cell: str) -> None:
        ...

    def __hash__(self) -> int:
        return hash(self.ip)

    def __eq__(self, other: "BaseBlackFormatter") -> bool:
        return isinstance(other, BaseBlackFormatter) and (self.ip is other.ip)

    def __call__(self, result) -> None:
        cell_id = len(self.ip.user_ns.get("In", 1)) - 1
        if cell_id == 0:
            return
        raw_cell = result.info.raw_cell
        try:
            fmt_cell = format_cell(raw_cell, fast=False, mode=FileMode())
        except NothingChanged:
            return
        self._set_cell(cell_id, raw_cell, fmt_cell)


class BlackLabFormatter(BaseBlackFormatter):
    """Black formatter for JupyterLab."""

    def _set_cell(self, cell_id: int, raw_cell: str, fmt_cell: str) -> None:
        self.ip.set_next_input(fmt_cell, replace=True)


class BlackNotebookFormatter(BaseBlackFormatter):
    """Black formatter for Jupyter notebooks."""

    def _set_cell(self, cell_id: int, raw_cell: str, fmt_cell: str) -> None:
        js_code = """
        setTimeout(function() {{
            var nbb_cell_id = {cell_id};
            var nbb_unformatted_code = {raw_cell};
            var nbb_formatted_code = {fmt_cell};
            var nbb_cells = Jupyter.notebook.get_cells();
            for (var i = 0; i < nbb_cells.length; ++i) {{
                if (nbb_cells[i].input_prompt_number == nbb_cell_id) {{
                    if (nbb_cells[i].get_text() == nbb_unformatted_code) {{
                         nbb_cells[i].set_text(nbb_formatted_code);
                    }}
                    break;
                }}
            }}
        }}, 500);
        """.format(
            cell_id=cell_id,
            raw_cell=json.dumps(raw_cell),
            fmt_cell=json.dumps(fmt_cell),
        )
        display(Javascript(js_code))


def is_lab_notebook() -> bool:
    """Check if the current process is a JupyterLab process."""
    return any(
        re.search("jupyter-lab", part) for part in psutil.Process().parent().cmdline()
    )


def _construct_formatter(ipython):
    """Construct a Black formatter from an ipython instance, based on whether we're in
    a JupyterLab notebook or not.
    """
    if is_lab_notebook():
        return BlackLabFormatter(ipython)
    return BlackNotebookFormatter(ipython)


def load_ipython_extension(ipython):
    ipython.events.register("post_run_cell", _construct_formatter(ipython))


def unload_ipython_extension(ipython):
    ipython.events.unregister("post_run_cell", _construct_formatter(ipython))
