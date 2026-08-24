#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""The lazy corpus boundary for Verbal Reasoning."""
from __future__ import annotations

import importlib
import random
import sys
import unittest
from pathlib import Path

from neural_workshop import verbal


class FakeTable:
    def __init__(self, row):
        self.row = row

    def slice(self, start, count):
        return self

    def to_pylist(self):
        return [self.row]


class FakeReader:
    def __init__(self, rows):
        self.rows = rows
        self.num_row_groups = len(rows)
        self.reads = []

    def read_row_group(self, group, columns):
        self.reads.append((group, tuple(columns)))
        return FakeTable(self.rows[group])


def row(**changes):
    made = {
        'prompt': 'Which conclusion follows?',
        'choices': ['First', 'Second', 'Third'],
        'answer': '1',
        'answer_text': 'Second',
        'explanation': 'The second choice follows.',
        'task_type': 'deductive_logic',
        'language': 'en',
    }
    made.update(changes)
    return made


class LazyBankTests(unittest.TestCase):

    def test_construction_opens_nothing(self):
        opened = []
        bank = verbal.QuestionBank(
            files=[Path('questions.parquet')],
            reader_factory=lambda path: opened.append(path))
        self.assertFalse(bank.opened)
        self.assertEqual(opened, [])

    def test_first_draw_opens_metadata_and_reads_one_group(self):
        reader = FakeReader([row()])
        opened = []
        bank = verbal.QuestionBank(
            files=[Path('questions.parquet')],
            reader_factory=lambda path: opened.append(path) or reader)
        question = bank.draw(random.Random(4))
        self.assertEqual(opened, ['questions.parquet'])
        self.assertEqual(len(reader.reads), 1)
        self.assertEqual(question.choices[question.answer], 'Second')

    def test_rejected_rows_are_skipped_without_loading_the_corpus(self):
        reader = FakeReader([
            row(language='ru'),
            row(choices=[]),
            row(prompt='x' * (verbal.MAX_PROMPT + 1)),
            row(),
        ])

        class InOrder:
            def __init__(self):
                self.index = 0

            def randrange(self, stop):
                answer = self.index
                self.index += 1
                return answer

            def shuffle(self, values):
                values.reverse()

        question = verbal.QuestionBank(
            files=[Path('questions.parquet')],
            reader_factory=lambda path: reader).draw(InOrder())
        self.assertEqual(len(reader.reads), 4)
        self.assertEqual(question.choices[question.answer], 'Second')

    def test_import_does_not_import_pyarrow(self):
        before = set(sys.modules)
        importlib.reload(verbal)
        added = set(sys.modules) - before
        self.assertFalse(any(name == 'pyarrow' or name.startswith('pyarrow.')
                             for name in added))


if __name__ == '__main__':
    unittest.main()
