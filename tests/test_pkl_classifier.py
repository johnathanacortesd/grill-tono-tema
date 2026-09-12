# ======================================
# Pruebas de clasificadores PKL opcionales
# ======================================
import io
import os
import sys
import unittest

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pkl_classifier import (  # noqa: E402
    PklClassifierError,
    apply_pkl_classifiers,
    classification_plan,
    format_theme_label,
    load_sklearn_estimator,
    map_tone_label,
    text_for_classification,
)
from pipeline import BASE_OUTPUT_COLUMNS, KEY_MAP, process_dossier  # noqa: E402


def _make_pipeline(texts, labels):
    pipe = Pipeline(
        [
            ("tfidf", TfidfVectorizer()),
            ("clf", MultinomialNB()),
        ]
    )
    pipe.fit(list(texts), list(labels))
    return pipe


def _dump_bytes(obj) -> bytes:
    buf = io.BytesIO()
    joblib.dump(obj, buf)
    return buf.getvalue()


def _tone_pipeline():
    texts = [
        "denuncia grave escandalo corrupcion",
        "queja pesima crisis fraude",
        "informe reunion cifras oficiales",
        "boletin datos tecnicos generales",
        "excelente logro homenaje reconocimiento",
        "felicitaciones alianza beneficio",
    ]
    labels = [-1, -1, 0, 0, 1, 1]
    return _make_pipeline(texts, labels)


def _theme_pipeline():
    texts = [
        "atencion a pacientes en la clinica",
        "cuidado hospitalario de pacientes",
        "entrevista con el rector declara",
        "dialogo entrevista exclusiva",
        "evento de inauguracion del proyecto",
        "proyecto especial y evento academico",
        "fallecimiento de un docente",
        "obituario y fallecimientos",
        "mencion breve de la marca",
        "mencion en un listado",
    ]
    labels = [
        "Atención a pacientes",
        "Atención a pacientes",
        "Entrevista",
        "Entrevista",
        "Eventos o Proyectos",
        "Eventos o Proyectos",
        "Fallecimientos",
        "Fallecimientos",
        "Mención",
        "Mención",
    ]
    return _make_pipeline(texts, labels)


def _sample_rows():
    return [
        {
            "Título": "Excelente logro institucional",
            "Resumen - Aclaracion": "felicitaciones alianza beneficio",
            "Contexto analizado": "excelente logro homenaje reconocimiento",
            "Tono_IA": "Neutro",
            "Tema_IA": "Gestión Institucional",
            "Subtema_IA": "Hecho Informativo",
            "is_duplicate": False,
        },
        {
            "Título": "Denuncia grave",
            "Resumen - Aclaracion": "denuncia grave escandalo corrupcion",
            "Contexto analizado": "denuncia grave escandalo corrupcion",
            "Tono_IA": "Positivo",
            "Tema_IA": "Gestión Institucional",
            "Subtema_IA": "Queja ciudadana",
            "is_duplicate": False,
        },
        {
            "Título": "Duplicada",
            "Resumen - Aclaracion": "n/a",
            "Contexto analizado": "-",
            "Tono_IA": "Duplicada",
            "Tema_IA": "-",
            "Subtema_IA": "-",
            "is_duplicate": True,
        },
    ]


def _mini_xlsx_bytes() -> bytes:
    df = pd.DataFrame(
        {
            "NoticiaId": [101, 102],
            "Fecha": ["01/01/2026", "02/01/2026"],
            "Hora": ["10:00:00", "11:00:00"],
            "Medio": ["eltiempo", "eltiempo"],
            "Tipo de Medio": ["internet", "internet"],
            "Título": [
                "Excelente logro institucional",
                "Denuncia grave por irregularidades",
            ],
            "CuerpoEs": [
                "felicitaciones alianza beneficio reconocimiento",
                "denuncia grave escandalo corrupcion",
            ],
            "URL Nota": ["https://example.com/a", "https://example.com/b"],
            "Empresa rel.": ["Marca Demo", "Marca Demo"],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


class ToneMappingTests(unittest.TestCase):
    def test_numeric_labels(self):
        self.assertEqual(map_tone_label(-1), "Negativo")
        self.assertEqual(map_tone_label(0), "Neutro")
        self.assertEqual(map_tone_label(1), "Positivo")

    def test_numpy_and_strings(self):
        self.assertEqual(map_tone_label(np.int64(-1)), "Negativo")
        self.assertEqual(map_tone_label("-1"), "Negativo")
        self.assertEqual(map_tone_label("0"), "Neutro")
        self.assertEqual(map_tone_label("1"), "Positivo")
        self.assertEqual(map_tone_label("positivo"), "Positivo")
        self.assertEqual(map_tone_label("Negativo"), "Negativo")

    def test_theme_labels_passthrough(self):
        self.assertEqual(format_theme_label("Atención a pacientes"), "Atención a pacientes")
        self.assertEqual(format_theme_label("Eventos o Proyectos"), "Eventos o Proyectos")


class LoadPklTests(unittest.TestCase):
    def test_valid_pipeline_roundtrip(self):
        model = _tone_pipeline()
        loaded, classes = load_sklearn_estimator(_dump_bytes(model), "tono")
        self.assertTrue(hasattr(loaded, "predict"))
        self.assertIsNotNone(classes)
        self.assertEqual(set(int(c) for c in classes), {-1, 0, 1})
        self.assertEqual(list(loaded.named_steps), ["tfidf", "clf"])

    def test_invalid_bytes(self):
        with self.assertRaises(PklClassifierError) as ctx:
            load_sklearn_estimator(b"esto no es un pkl", "tono")
        self.assertIn("tono", str(ctx.exception).lower())
        self.assertIn("inválido", str(ctx.exception).lower())

    def test_invalid_object_without_predict(self):
        with self.assertRaises(PklClassifierError) as ctx:
            load_sklearn_estimator(_dump_bytes({"foo": 1}), "tema")
        self.assertIn("tema", str(ctx.exception).lower())
        self.assertIn("predict", str(ctx.exception).lower())


class ApplyPklPathTests(unittest.TestCase):
    def test_no_pkl_keeps_existing_values(self):
        rows = _sample_rows()
        original = [dict(r) for r in rows]
        plan = classification_plan(ai_enabled=True, tone_model=None, theme_model=None)
        self.assertTrue(plan["use_llm_tone"])
        self.assertTrue(plan["use_llm_theme"])
        self.assertTrue(plan["use_llm_subtema"])
        self.assertFalse(plan["use_pkl_tone"])
        self.assertFalse(plan["use_pkl_theme"])
        out = apply_pkl_classifiers(rows, KEY_MAP, None, None)
        for got, exp in zip(out, original):
            self.assertEqual(got["Tono_IA"], exp["Tono_IA"])
            self.assertEqual(got["Tema_IA"], exp["Tema_IA"])
            self.assertEqual(got["Subtema_IA"], exp["Subtema_IA"])

    def test_tono_only_overrides_tone_keeps_theme_and_subtema(self):
        rows = _sample_rows()
        tone_model = _tone_pipeline()
        plan = classification_plan(True, tone_model, None)
        self.assertTrue(plan["use_pkl_tone"])
        self.assertFalse(plan["use_pkl_theme"])
        self.assertTrue(plan["use_llm_theme"])
        self.assertTrue(plan["use_llm_subtema"])
        out = apply_pkl_classifiers(rows, KEY_MAP, tone_model, None)
        self.assertIn(out[0]["Tono_IA"], {"Positivo", "Negativo", "Neutro"})
        self.assertEqual(out[0]["Tema_IA"], "Gestión Institucional")
        self.assertEqual(out[0]["Subtema_IA"], "Hecho Informativo")
        self.assertEqual(out[1]["Tema_IA"], "Gestión Institucional")
        self.assertEqual(out[1]["Subtema_IA"], "Queja ciudadana")
        self.assertEqual(out[2]["Tono_IA"], "Duplicada")
        self.assertEqual(out[2]["Tema_IA"], "-")

    def test_tema_only_overrides_theme_keeps_tone_and_subtema(self):
        rows = _sample_rows()
        rows[0]["Contexto analizado"] = "entrevista con el rector declara"
        theme_model = _theme_pipeline()
        plan = classification_plan(True, None, theme_model)
        self.assertFalse(plan["use_pkl_tone"])
        self.assertTrue(plan["use_pkl_theme"])
        self.assertTrue(plan["use_llm_tone"])
        out = apply_pkl_classifiers(rows, KEY_MAP, None, theme_model)
        self.assertEqual(out[0]["Tono_IA"], "Neutro")
        self.assertEqual(out[0]["Subtema_IA"], "Hecho Informativo")
        self.assertTrue(out[0]["Tema_IA"])
        self.assertNotEqual(out[0]["Tema_IA"], "Gestión Institucional")

    def test_both_pkls_override_tone_and_theme_not_subtema(self):
        rows = _sample_rows()
        out = apply_pkl_classifiers(rows, KEY_MAP, _tone_pipeline(), _theme_pipeline())
        self.assertIn(out[0]["Tono_IA"], {"Positivo", "Negativo", "Neutro"})
        self.assertTrue(out[0]["Tema_IA"])
        self.assertEqual(out[0]["Subtema_IA"], "Hecho Informativo")
        self.assertEqual(out[1]["Subtema_IA"], "Queja ciudadana")
        self.assertEqual(out[2]["Tono_IA"], "Duplicada")

    def test_predict_uses_contexto_not_title(self):
        tone_model = _tone_pipeline()
        rows = [
            {
                "Título": "denuncia grave escandalo corrupcion",
                "Resumen - Aclaracion": "denuncia grave escandalo corrupcion",
                "Contexto analizado": "excelente logro homenaje reconocimiento",
                "Tono_IA": "Neutro",
                "Tema_IA": "X",
                "Subtema_IA": "Y",
                "is_duplicate": False,
            }
        ]
        self.assertIn("excelente", text_for_classification(rows[0], KEY_MAP))
        out = apply_pkl_classifiers(rows, KEY_MAP, tone_model, None)
        self.assertEqual(out[0]["Tono_IA"], "Positivo")
        self.assertEqual(out[0]["Subtema_IA"], "Y")


class PipelineNoPklVsPklTests(unittest.TestCase):
    def setUp(self):
        self.region_map = {"eltiempo": "Nacional"}
        self.internet_map = {"eltiempo": "El Tiempo"}
        self.xlsx = _mini_xlsx_bytes()

    def test_no_pkl_old_path_omits_ai_columns(self):
        result = process_dossier(
            self.xlsx,
            self.region_map,
            self.internet_map,
            ai_config=None,
        )
        df = pd.read_excel(io.BytesIO(result["output_data"]))
        self.assertNotIn("Tono_IA", df.columns)
        self.assertNotIn("Tema_IA", df.columns)
        self.assertNotIn("Subtema_IA", df.columns)
        for col in BASE_OUTPUT_COLUMNS:
            self.assertIn(col, df.columns)

    def test_tono_only_pipeline_exports_tone_not_llm_theme(self):
        result = process_dossier(
            self.xlsx,
            self.region_map,
            self.internet_map,
            ai_config={
                "enabled": False,
                "brand": "Marca Demo",
                "aliases": [],
                "tone_pkl_bytes": _dump_bytes(_tone_pipeline()),
                "theme_pkl_bytes": None,
            },
        )
        df = pd.read_excel(io.BytesIO(result["output_data"]))
        self.assertIn("Tono_IA", df.columns)
        self.assertIn("Tema_IA", df.columns)
        self.assertIn("Subtema_IA", df.columns)
        unique = df[df["Tono_IA"] != "Duplicada"]
        self.assertTrue(set(unique["Tono_IA"]).issubset({"Positivo", "Negativo", "Neutro"}))
        self.assertTrue((unique["Tema_IA"] == "-").all())
        self.assertTrue((unique["Subtema_IA"] == "-").all())

    def test_tema_only_pipeline_exports_theme(self):
        result = process_dossier(
            self.xlsx,
            self.region_map,
            self.internet_map,
            ai_config={
                "enabled": False,
                "brand": "Marca Demo",
                "aliases": [],
                "tone_pkl_bytes": None,
                "theme_pkl_bytes": _dump_bytes(_theme_pipeline()),
            },
        )
        df = pd.read_excel(io.BytesIO(result["output_data"]))
        unique = df[df["Tema_IA"] != "-"]
        self.assertTrue(len(unique) >= 1)
        self.assertTrue((df["Tono_IA"].isin(["-", "Duplicada"])).all())
        self.assertTrue((df["Subtema_IA"].isin(["-", "Duplicada"])).all() or (df["Subtema_IA"] == "-").all())

    def test_both_pkls_pipeline(self):
        result = process_dossier(
            self.xlsx,
            self.region_map,
            self.internet_map,
            ai_config={
                "enabled": False,
                "brand": "Marca Demo",
                "aliases": [],
                "tone_pkl_bytes": _dump_bytes(_tone_pipeline()),
                "theme_pkl_bytes": _dump_bytes(_theme_pipeline()),
            },
        )
        df = pd.read_excel(io.BytesIO(result["output_data"]))
        unique = df[df["Tono_IA"] != "Duplicada"]
        self.assertTrue(set(unique["Tono_IA"]).issubset({"Positivo", "Negativo", "Neutro"}))
        self.assertTrue((unique["Tema_IA"] != "-").all())
        self.assertTrue((unique["Subtema_IA"] == "-").all())

    def test_invalid_pkl_in_pipeline(self):
        with self.assertRaises(PklClassifierError):
            process_dossier(
                self.xlsx,
                self.region_map,
                self.internet_map,
                ai_config={
                    "enabled": False,
                    "tone_pkl_bytes": b"no-es-un-modelo",
                },
            )


if __name__ == "__main__":
    unittest.main()
