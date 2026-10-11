"""tests/test_label_pr_state.py — Tests unitarios para scripts/ci/label_pr_state.py (#102).

Verifica que determine_label no marque pr:merged en PRs abiertas evaluando
correctamente la propiedad booleana `merged` de PyGithub.
"""

import sys
import unittest
from unittest.mock import MagicMock

# Importar el módulo del script de CI
sys.path.insert(0, "scripts/ci")
import label_pr_state


class TestLabelPRState(unittest.TestCase):
    def test_pr_no_mergeada_no_recibe_pr_merged(self):
        """Una PR abierta no debe recibir la etiqueta pr:merged."""
        pr = MagicMock()
        pr.merged = False
        pr.draft = False
        pr.mergeable = True
        
        # Simular que los checks pasaron
        commits = MagicMock()
        commits.totalCount = 1
        commit = MagicMock()
        check_runs = MagicMock()
        check_runs.totalCount = 1
        check_run = MagicMock()
        check_run.status = "completed"
        check_run.conclusion = "success"
        check_run.name = "Unit tests"
        check_runs.__iter__.return_value = [check_run]
        commit.get_check_runs.return_value = check_runs
        commits.__getitem__.return_value = commit
        pr.get_commits.return_value = commits

        # Sin reviews humanas aún
        pr.get_reviews.return_value = MagicMock(totalCount=0)

        label = label_pr_state.determine_label(pr)
        self.assertNotEqual(label, label_pr_state.LABEL_MERGED)
        self.assertEqual(label, label_pr_state.LABEL_NEEDS_REVIEW)

    def test_pr_mergeada_recibe_pr_merged(self):
        """Una PR efectivamente mergeada sí debe recibir pr:merged."""
        pr = MagicMock()
        pr.merged = True
        
        label = label_pr_state.determine_label(pr)
        self.assertEqual(label, label_pr_state.LABEL_MERGED)

    def test_pr_draft_recibe_pr_draft(self):
        """Una PR en borrador debe recibir pr:draft."""
        pr = MagicMock()
        pr.merged = False
        pr.draft = True

        label = label_pr_state.determine_label(pr)
        self.assertEqual(label, label_pr_state.LABEL_DRAFT)

    def test_pr_con_conflictos_recibe_pr_blocked(self):
        """Una PR con conflictos de fusión debe recibir pr:blocked."""
        pr = MagicMock()
        pr.merged = False
        pr.draft = False
        pr.mergeable = False

        label = label_pr_state.determine_label(pr)
        self.assertEqual(label, label_pr_state.LABEL_BLOCKED)


if __name__ == "__main__":
    unittest.main()
