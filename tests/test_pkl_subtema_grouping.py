# ======================================
# Subtema + agrupación cuando hay PKL de tema
# ======================================
import unittest
from unittest.mock import patch

import numpy as np

from ai_analyzer import (
    enrich_rows_with_ai,
    ensure_subtema_distinct_from_tema,
)
from pipeline import KEY_MAP
from pkl_classifier import apply_pkl_classifiers, classification_plan


class _PredictByKeyword:
    def __init__(self, mapping, default):
        self.mapping = mapping
        self.default = default

    def predict(self, texts):
        out = []
        for t in texts:
            tl = str(t).lower()
            hit = self.default
            for needle, label in self.mapping:
                if needle in tl:
                    hit = label
                    break
            out.append(hit)
        return np.array(out)


def _news_row(title, ctx, subtema="Apertura de sede norte"):
    return {
        "Título": title,
        "Resumen - Aclaracion": ctx,
        "Contexto analizado": ctx,
        "Tono_IA": "Neutro",
        "Tema_IA": "Gestión Institucional",
        "Subtema_IA": subtema,
        "is_duplicate": False,
    }


class SubtemaQualityWithTemaPklTests(unittest.TestCase):
    def test_plan_skips_llm_theme_but_keeps_llm_subtema(self):
        plan = classification_plan(True, None, object())
        self.assertFalse(plan["use_llm_theme"])
        self.assertTrue(plan["use_llm_subtema"])
        self.assertTrue(plan["use_llm_tone"])

    def test_ensure_subtema_not_collapsed_to_pkl_theme(self):
        sub = ensure_subtema_distinct_from_tema(
            "Entrevista",
            "Entrevista",
            "UdeA",
            "Diálogo con el rector sobre nuevas becas",
            "La universidad anunció diálogo con el rector sobre nuevas becas de posgrado.",
        )
        self.assertTrue(sub)
        self.assertNotEqual(sub.strip().lower(), "entrevista")
        self.assertGreaterEqual(len(sub.split()), 4)

    def test_tema_pkl_keeps_specific_llm_subtema_and_skips_llm_theme(self):
        rows = [
            _news_row(
                "Apertura de la nueva sede norte en Cali",
                "La universidad inauguró una sede para ampliar cobertura educativa en el norte.",
            )
        ]
        theme_model = _PredictByKeyword([], "Mención")
        with patch("ai_analyzer.OpenAI"):
            with patch("ai_analyzer._call_openai_cluster") as mock_llm:
                mock_llm.return_value = (
                    "Neutro",
                    "Educación Superior",
                    "Apertura de sede norte",
                )
                out = enrich_rows_with_ai(
                    rows, KEY_MAP, "UdeA", [], "sk-test", theme_model=theme_model
                )
        self.assertEqual(mock_llm.call_count, 1)
        self.assertFalse(mock_llm.call_args.kwargs["request_theme"])
        self.assertTrue(mock_llm.call_args.kwargs["request_tone"])
        self.assertEqual(mock_llm.call_args.kwargs["pkl_theme"], "Mención")
        self.assertEqual(out[0]["Tema_IA"], "Mención")
        self.assertEqual(out[0]["Subtema_IA"], "Apertura de sede norte")
        self.assertGreaterEqual(len(out[0]["Subtema_IA"].split()), 4)
        self.assertNotEqual(out[0]["Subtema_IA"].lower(), "mención")

    def test_no_pkl_still_requests_llm_theme_and_subtema(self):
        rows = [
            _news_row(
                "Apertura de la nueva sede norte en Cali",
                "La universidad inauguró una sede para ampliar cobertura educativa en el norte.",
            )
        ]
        with patch("ai_analyzer.OpenAI"):
            with patch("ai_analyzer._call_openai_cluster") as mock_llm:
                mock_llm.return_value = (
                    "Positivo",
                    "Educación Superior",
                    "Apertura de sede norte",
                )
                out = enrich_rows_with_ai(rows, KEY_MAP, "UdeA", [], "sk-test")
        self.assertTrue(mock_llm.call_args.kwargs.get("request_theme", True))
        self.assertTrue(mock_llm.call_args.kwargs.get("request_tone", True))
        self.assertEqual(out[0]["Tema_IA"], "Educación Superior")
        self.assertEqual(out[0]["Subtema_IA"], "Apertura de sede norte")

    def test_similar_news_share_pkl_tema_and_llm_subtema(self):
        title = "Inauguración sede norte en Cali"
        rows = [
            _news_row(title, "entrevista con el rector declara la inauguración"),
            _news_row(title, "atencion a pacientes en la clinica durante la inauguración"),
        ]
        theme_model = _PredictByKeyword(
            [("pacientes", "Atención a pacientes"), ("entrevista", "Entrevista")],
            "Mención",
        )
        with patch("ai_analyzer.OpenAI"):
            with patch("ai_analyzer._call_openai_cluster") as mock_llm:
                mock_llm.return_value = (
                    "Neutro",
                    "Educación Superior",
                    "Apertura de sede norte",
                )
                out = enrich_rows_with_ai(
                    rows, KEY_MAP, "UdeA", [], "sk-test", theme_model=theme_model
                )
        self.assertEqual(mock_llm.call_count, 1)
        self.assertEqual(out[0]["Tema_IA"], out[1]["Tema_IA"])
        self.assertEqual(out[0]["Subtema_IA"], out[1]["Subtema_IA"])
        self.assertEqual(out[0]["Subtema_IA"], "Apertura de sede norte")
        self.assertEqual(out[0]["Tono_IA"], out[1]["Tono_IA"])


class PklGroupingWithoutAiTests(unittest.TestCase):
    def test_similar_titles_keep_same_pkl_theme(self):
        title = "Inauguración sede norte en Cali"
        rows = [
            _news_row(title, "entrevista con el rector declara"),
            _news_row(title, "atencion a pacientes en la clinica"),
        ]
        theme_model = _PredictByKeyword(
            [("pacientes", "Atención a pacientes"), ("entrevista", "Entrevista")],
            "Mención",
        )
        out = apply_pkl_classifiers(rows, KEY_MAP, None, theme_model)
        self.assertEqual(out[0]["Tema_IA"], out[1]["Tema_IA"])
        self.assertEqual(out[0]["Subtema_IA"], "Apertura de sede norte")
        self.assertEqual(out[1]["Subtema_IA"], "Apertura de sede norte")


if __name__ == "__main__":
    unittest.main()
