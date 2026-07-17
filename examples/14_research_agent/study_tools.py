"""Agents SDK wrappers around the study's read-only file access."""
from agents import function_tool

from study_files import list_study_files as _list_study_files
from study_files import read_study_file as _read_study_file


@function_tool
def list_study_files() -> list[dict]:
    """List every readable file in the fixed demo study folder."""
    return _list_study_files()


@function_tool
def read_study_file(path: str) -> str:
    """Read one study file. Use a path returned by list_study_files."""
    return _read_study_file(path)


TOOLS = [list_study_files, read_study_file]
