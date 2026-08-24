# -*- coding: utf-8 -*-
"""Lazy access to the local Verbal IQ Parquet corpus.

Importing this module does not import :mod:`pyarrow`, inspect the dataset, or
open a file.  A :class:`QuestionBank` does that only when its first question
is requested; thereafter one question costs one Parquet row-group read.

SPDX-License-Identifier: GPL-2.0-or-later
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Type


DATASET_ENV = 'NW_VERBAL_IQ_DATASET'
DEFAULT_DATASET = Path(
    '/Users/torarinvikbjarko/Documents/Coding Projects/Python Projects/'
    'VerbalIQDataset')
MAX_CHOICES = 5
MAX_PROMPT = 1400
MAX_CHOICE = 260


class DatasetUnavailable(RuntimeError):
    """The configured corpus cannot be opened."""


@dataclass(frozen=True)
class Question:
    prompt: str
    choices: Sequence[str]
    answer: int
    answer_text: str
    explanation: str
    task_type: str


def dataset_root() -> Path:
    """Configured dataset checkout, without touching the filesystem."""
    configured = os.environ.get(DATASET_ENV)
    if configured:
        return Path(configured).expanduser()
    sibling = Path.cwd().resolve().parent / 'VerbalIQDataset'
    return sibling if sibling.exists() else DEFAULT_DATASET


def parquet_files(root: Optional[Path] = None) -> List[Path]:
    """Find the best local artifact, preferring the verified release."""
    root = Path(root) if root is not None else dataset_root()
    candidates = (
        root / 'build' / 'verbal-iq-release' / 'data',
        root / 'build' / 'verbal-iq-public' / 'data',
        root / 'build' / 'verbal-iq' / 'data',
        root,
    )
    for data in candidates:
        files = sorted(data.glob('train/*.parquet'))
        if not files:
            files = sorted(data.glob('*.parquet'))
        if files:
            return files
    raise DatasetUnavailable(
        'No Verbal IQ Parquet artifact found under %s. Set %s to the '
        'dataset checkout or a Parquet data directory.' % (root, DATASET_ENV))


def _parquet_file_class() -> Type[object]:
    """Import the optional reader at first use, never at application start."""
    try:
        from pyarrow.parquet import ParquetFile
    except ImportError as exc:
        raise DatasetUnavailable(
            'Verbal Reasoning needs pyarrow to read the local corpus. '
            'Install it with "python -m pip install pyarrow".') from exc
    return ParquetFile


class QuestionBank:
    """Random-access view that opens metadata once and individual rows lazily."""

    columns = ('prompt', 'choices', 'answer', 'answer_text', 'explanation',
               'task_type', 'language')

    def __init__(self, root: Optional[Path] = None,
                 reader_factory: Optional[Callable[[str], object]] = None,
                 files: Optional[Sequence[Path]] = None) -> None:
        self.root = root
        self._reader_factory = reader_factory
        self._paths = list(files) if files is not None else None
        self._readers: Optional[List[object]] = None
        self._offsets: List[int] = []
        self._rows = 0

    @property
    def opened(self) -> bool:
        return self._readers is not None

    def _open(self) -> None:
        if self._readers is not None:
            return
        paths = self._paths if self._paths is not None else parquet_files(self.root)
        factory = self._reader_factory or _parquet_file_class()
        try:
            readers = [factory(str(path)) for path in paths]
        except Exception as exc:
            raise DatasetUnavailable('Could not open Verbal IQ data: %s' % exc) from exc
        self._readers = readers
        self._offsets = []
        self._rows = 0
        for reader in readers:
            self._offsets.append(self._rows)
            # This corpus is deliberately written one row per row group, which
            # makes a random question a small, bounded read.
            self._rows += int(reader.num_row_groups)
        if not self._rows:
            raise DatasetUnavailable('The Verbal IQ Parquet artifact is empty.')

    def _row(self, index: int) -> dict:
        assert self._readers is not None
        file_number = len(self._offsets) - 1
        for number, start in enumerate(self._offsets):
            if number + 1 == len(self._offsets) or index < self._offsets[number + 1]:
                file_number = number
                break
        group = index - self._offsets[file_number]
        table = self._readers[file_number].read_row_group(
            group, columns=list(self.columns))
        return table.slice(0, 1).to_pylist()[0]

    @staticmethod
    def _question(row: dict) -> Optional[Question]:
        choices = [str(value).strip() for value in (row.get('choices') or [])]
        answer = str(row.get('answer', ''))
        prompt = str(row.get('prompt', '')).strip()
        if (row.get('language') != 'en' or not answer.isdigit()
                or not 2 <= len(choices) <= MAX_CHOICES
                or int(answer) >= len(choices) or len(prompt) > MAX_PROMPT
                or any(not value or len(value) > MAX_CHOICE for value in choices)):
            return None
        return Question(prompt, tuple(choices), int(answer),
                        str(row.get('answer_text', '')).strip(),
                        str(row.get('explanation', '')).strip(),
                        str(row.get('task_type', '')).strip())

    def draw(self, rng: object) -> Question:
        """Draw one displayable English multiple-choice question."""
        self._open()
        assert self._rows
        for _attempt in range(256):
            question = self._question(self._row(rng.randrange(self._rows)))
            if question is None:
                continue
            order = list(range(len(question.choices)))
            rng.shuffle(order)
            return Question(
                question.prompt,
                tuple(question.choices[index] for index in order),
                order.index(question.answer), question.answer_text,
                question.explanation, question.task_type)
        raise DatasetUnavailable('No displayable multiple-choice question found.')


__all__ = ['DATASET_ENV', 'DatasetUnavailable', 'MAX_CHOICES', 'Question',
           'QuestionBank', 'dataset_root', 'parquet_files']
