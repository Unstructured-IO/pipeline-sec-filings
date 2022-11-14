import os
from pathlib import Path
import pytest
from typing import List
import sys

if sys.version_info < (3, 8):
    from typing_extensions import Final
else:
    from typing import Final

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

TIMEOUT: Final[int] = 600  # in seconds

DIRECTORY: Final[str] = Path(__file__).absolute().parent
PIPELINE_NB_DIR: Final[str] = os.path.join(DIRECTORY, "..", "pipeline-notebooks")


def run_notebook_directory(directory: str):
    """Executes all of the notebooks in a test directory. Tests that at least one cell
    was executed in every notebook."""
    notebook_files = [file for file in os.listdir(directory) if file.endswith(".ipynb")]
    for notebook_file in notebook_files:
        filename = os.path.join(directory, notebook_file)

        with open(filename) as f:
            notebook = nbformat.read(f, as_version=4)

        executor = ExecutePreprocessor(timeout=TIMEOUT)
        executed_notebook, _ = executor.preprocess(notebook)

        execution_counts: List[int] = list()
        for cell in executed_notebook["cells"]:
            execution_count = cell.get("execution_count", None)
            if isinstance(execution_count, int):
                execution_counts.append(execution_count)

        assert len(execution_counts) > 0


@pytest.mark.parametrize("directory", [(PIPELINE_NB_DIR)])
def test_notebooks(directory):
    # NOTE(robinson) - The expectation is that all the notebooks will execute completely
    # without errors
    run_notebook_directory(directory)
