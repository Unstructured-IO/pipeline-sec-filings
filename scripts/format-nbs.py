#!/usr/bin/env python3

import argparse
from copy import deepcopy
from pathlib import Path
from typing import List, Tuple, Union

from nbdev import clean
from nbconvert.preprocessors import ExecutePreprocessor
import nbformat
from unstructured_api_tools.pipelines.convert import read_notebook


def process_nb(nb: dict, working_dir: Union[str, Path]) -> dict:
    ep = ExecutePreprocessor(timeout=600)
    ep.preprocess(nb, {"metadata": {"path": working_dir}})
    return nb


def nb_paths() -> List[Path]:
    root_path = Path(__file__).parent.parent
    return [
        fn
        for dir in root_path.iterdir()
        # NOTE(alan): Search only in paths with 'notebooks' in the title such as pipeline-notebooks
        # and exploration-notebooks
        if "notebooks" in dir.stem and dir.is_dir()
        for fn in dir.iterdir()
        if fn.suffix == ".ipynb"
    ]


def to_results_str(fns: List[Path], nonmatching_nbs: List[Path]) -> Tuple[str, str]:
    unchanged = len(fns) - len(nonmatching_nbs)
    results = []
    if nonmatching_nbs:
        results.append(
            f"{len(nonmatching_nbs)} "
            f"{'file' if len(nonmatching_nbs) == 1 else 'files'} "
            f"{'would be ' if check else ''}changed"
        )
    if unchanged:
        results.append(
            f"{unchanged} "
            f"{'file' if unchanged == 1 else 'files'} "
            f"{'would be ' if check else ''}left unchanged"
        )
    summary_str = ", ".join(results) + ".\n"
    if nonmatching_nbs:
        details_str = (
            f"The following notebooks {'would have been' if check else 'were'} "
            "changed when executed and cleaned:\n* " + "\n* ".join(nonmatching_nbs) + "\n"
        )
    else:
        details_str = ""

    return summary_str, details_str


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        default=False,
        action="store_true",
        help="Check notebook format without making changes. Return code 0 means formatting would "
        "produce no changes. Return code 1 means some files would be changed.",
    )
    args = parser.parse_args()
    check = args.check

    root_path = Path(__file__).parent.parent
    nonmatching_nbs = []
    fns = nb_paths()
    for fn in fns:
        nb = read_notebook(fn)
        modified_nb = deepcopy(nb)
        process_nb(modified_nb, root_path)
        clean.clean_nb(modified_nb, allowed_cell_metadata_keys=["tags"])
        if nb != modified_nb:
            nonmatching_nbs.append(str(fn))
        if not check:
            nbformat.write(modified_nb, fn)

    summary_str, details_str = to_results_str(fns, nonmatching_nbs)
    print(summary_str)
    if check:
        import sys

        sys.stderr.write(details_str)
        if nonmatching_nbs:
            sys.exit(1)
    else:
        print(details_str)