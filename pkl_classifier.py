# ======================================
# Clasificadores PKL opcionales (tono / tema)
# ======================================
import io
import logging
from typing import Any, Dict, List, Optional, Sequence

import joblib
import numpy as np

from ai_analyzer import cluster_similar_rows, extract_brand_context, generate_brand_variants

logger = logging.getLogger("pkl_classifier")

TONE_NUMERIC_TO_LABEL = {
    -1: "Negativo",
    0: "Neutro",
    1: "Positivo",
}

TONE_STRING_TO_LABEL = {
    "negativo": "Negativo",
    "negative": "Negativo",
    "neg": "Negativo",
    "neutro": "Neutro",
    "neutral": "Neutro",
    "neu": "Neutro",
    "positivo": "Positivo",
    "positive": "Positivo",
    "pos": "Positivo",
}


class PklClassifierError(Exception):
    """Error de usuario al cargar o aplicar un modelo PKL."""


def _spanish_axis(axis: str) -> str:
    mapping = {"tono": "tono", "tema": "tema", "tone": "tono", "theme": "tema"}
    return mapping.get((axis or "").strip().lower(), axis or "modelo")


def load_sklearn_estimator(data: bytes, axis: str = "modelo"):
    """Carga un estimador sklearn serializado con joblib y valida `predict`."""
    axis_es = _spanish_axis(axis)
    if not data:
        raise PklClassifierError(f"El archivo PKL de {axis_es} está vacío.")

    try:
        loaded = joblib.load(io.BytesIO(data))
    except Exception as exc:
        logger.warning("Fallo al cargar PKL de %s: %s", axis_es, exc)
        raise PklClassifierError(
            f"No se pudo leer el PKL de {axis_es}. "
            "El archivo es inválido, está dañado o no fue guardado con joblib."
        ) from exc

    estimator = _unwrap_estimator(loaded)
    if estimator is None or not hasattr(estimator, "predict") or not callable(getattr(estimator, "predict")):
        raise PklClassifierError(
            f"El PKL de {axis_es} no es un estimador de scikit-learn válido "
            "(debe exponer el método predict)."
        )

    classes = _extract_classes(estimator)
    if classes is None:
        logger.info("PKL de %s cargado sin classes_ visible; se continúa con predict.", axis_es)
    return estimator, classes


def _unwrap_estimator(loaded: Any):
    if loaded is None:
        return None
    if hasattr(loaded, "predict") and callable(getattr(loaded, "predict")):
        return loaded
    if isinstance(loaded, dict):
        for key in ("model", "pipeline", "clf", "estimator", "tono", "tema"):
            inner = loaded.get(key)
            if inner is not None and hasattr(inner, "predict"):
                return inner
    return loaded


def _extract_classes(estimator: Any) -> Optional[np.ndarray]:
    classes = getattr(estimator, "classes_", None)
    if classes is not None:
        return np.asarray(classes)
    named_steps = getattr(estimator, "named_steps", None)
    if named_steps:
        for step_name in ("clf", "classifier", "model"):
            step = named_steps.get(step_name)
            if step is not None and getattr(step, "classes_", None) is not None:
                return np.asarray(step.classes_)
        try:
            last = list(named_steps.values())[-1]
            if getattr(last, "classes_", None) is not None:
                return np.asarray(last.classes_)
        except Exception:
            pass
    return None


def map_tone_label(raw: Any) -> str:
    """Mapea etiquetas numéricas típicas [-1, 0, 1] a Negativo/Neutro/Positivo."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return "Neutro"

    if isinstance(raw, (bool, np.bool_)):
        return TONE_NUMERIC_TO_LABEL[1 if raw else 0]

    numeric = _try_int_label(raw)
    if numeric in TONE_NUMERIC_TO_LABEL:
        return TONE_NUMERIC_TO_LABEL[numeric]

    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none", "-"):
        return "Neutro"

    mapped = TONE_STRING_TO_LABEL.get(text.lower())
    if mapped:
        return mapped

    capitalized = text[:1].upper() + text[1:] if text else text
    if capitalized in ("Positivo", "Negativo", "Neutro"):
        return capitalized
    return text


def _try_int_label(raw: Any) -> Optional[int]:
    if isinstance(raw, (int, np.integer)):
        return int(raw)
    if isinstance(raw, (float, np.floating)):
        if np.isfinite(raw) and float(raw).is_integer():
            return int(raw)
        return None
    text = str(raw).strip()
    if text in ("-1", "0", "1"):
        return int(text)
    return None


def format_theme_label(raw: Any) -> str:
    """Conserva la etiqueta del modelo de tema sin hardcodear clases de cliente."""
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return ""
    return str(raw).strip()


def text_for_classification(row: dict, km: Optional[dict] = None) -> str:
    """Usa el mismo texto que el flujo IA: contexto, o título + resumen."""
    km = km or {}
    ctx = row.get("Contexto analizado")
    if ctx and str(ctx).strip() not in ("", "-", "nan", "None"):
        return str(ctx).strip()
    titulo_key = km.get("titulo", "Título")
    titulo = row.get(titulo_key) or row.get("Título") or ""
    resumen = (
        row.get("Resumen - Aclaracion")
        or row.get("resumen corto")
        or row.get("Resumen")
        or ""
    )
    return _title_resumen_text(titulo, resumen)


def _title_resumen_text(titulo: Any, resumen: Any) -> str:
    from ai_analyzer import clean_text_strictly_no_links

    t_clean = clean_text_strictly_no_links(str(titulo or ""))
    r_clean = clean_text_strictly_no_links(str(resumen or ""))
    if t_clean and r_clean:
        return f"{t_clean}. {r_clean}"[:800]
    return (t_clean or r_clean)[:800]


def fill_classification_context(
    rows: List[dict],
    km: dict,
    brand: str = "",
    aliases: Optional[Sequence[str]] = None,
) -> List[dict]:
    """Rellena 'Contexto analizado' si aún no existe (ruta PKL sin IA)."""
    aliases = list(aliases or [])
    brand_regexes = generate_brand_variants(brand, aliases) if brand else []
    titulo_key = km.get("titulo", "Título")
    for row in rows:
        if row.get("is_duplicate"):
            row["Contexto analizado"] = "-"
            continue
        existing = row.get("Contexto analizado")
        if existing and str(existing).strip() not in ("", "-", "nan", "None"):
            continue
        resumen_val = (
            row.get("Resumen - Aclaracion")
            or row.get("resumen corto")
            or row.get("Resumen")
            or ""
        )
        titulo_val = row.get(titulo_key) or row.get("Título") or ""
        if brand_regexes:
            row["Contexto analizado"] = extract_brand_context(
                str(resumen_val), str(titulo_val), brand_regexes
            )
        else:
            row["Contexto analizado"] = _title_resumen_text(titulo_val, resumen_val)
    return rows


def apply_pkl_classifiers(
    rows: List[dict],
    km: dict,
    tone_model=None,
    theme_model=None,
    progress_callback=None,
    brand: str = "",
    aliases: Optional[Sequence[str]] = None,
    unify_similar: bool = True,
) -> List[dict]:
    """Sobrescribe Tono_IA y/o Tema_IA. Nunca toca Subtema_IA. Omite duplicadas.

    Por defecto unifica noticias similares (mismo clúster que el flujo IA) para
    que compartan tono/tema y no se rompa el agrupamiento.
    """
    if not tone_model and not theme_model:
        return rows

    for i, row in enumerate(rows):
        if row.get("is_duplicate"):
            row.setdefault("Tono_IA", "Duplicada")
            row.setdefault("Tema_IA", "-")
            row.setdefault("Subtema_IA", "-")
            row.setdefault("Contexto analizado", "-")
            continue
        if not row.get("Contexto analizado"):
            row["Contexto analizado"] = text_for_classification(row, km) or "-"
        row.setdefault("Subtema_IA", "-")
        row.setdefault("Tono_IA", "-")
        row.setdefault("Tema_IA", "-")

    active = [i for i, row in enumerate(rows) if not row.get("is_duplicate")]
    if not active:
        return rows

    if unify_similar:
        regexes = generate_brand_variants(brand, list(aliases or [])) if brand else []
        cluster_map = cluster_similar_rows(rows, km, regexes)
    else:
        cluster_map = {i: i for i in active}

    members: Dict[int, List[int]] = {}
    reps: Dict[int, int] = {}
    for i in active:
        cid = cluster_map.get(i, i)
        members.setdefault(cid, []).append(i)
        if cid not in reps:
            reps[cid] = i

    ordered_cids = list(reps.keys())
    rep_texts = [text_for_classification(rows[reps[cid]], km) or "" for cid in ordered_cids]

    if tone_model is not None:
        if progress_callback:
            progress_callback(min(93, 88), "Clasificando tono con modelo PKL del cliente…")
        preds = _safe_predict(tone_model, rep_texts, "tono")
        for cid, pred in zip(ordered_cids, preds):
            label = map_tone_label(pred)
            for idx in members[cid]:
                rows[idx]["Tono_IA"] = label

    if theme_model is not None:
        if progress_callback:
            progress_callback(min(93, 90), "Clasificando tema con modelo PKL del cliente…")
        preds = _safe_predict(theme_model, rep_texts, "tema")
        for cid, pred in zip(ordered_cids, preds):
            label = format_theme_label(pred) or rows[reps[cid]].get("Tema_IA") or "-"
            for idx in members[cid]:
                rows[idx]["Tema_IA"] = label

    return rows


def _safe_predict(model, texts: Sequence[str], axis: str) -> List[Any]:
    axis_es = _spanish_axis(axis)
    try:
        preds = model.predict(list(texts))
    except Exception as exc:
        logger.exception("Fallo al aplicar predict del PKL de %s", axis_es)
        raise PklClassifierError(
            f"El PKL de {axis_es} se cargó pero falló al clasificar. "
            "Verifica que sea un pipeline de texto (p. ej. tfidf + clf)."
        ) from exc
    if preds is None:
        raise PklClassifierError(f"El PKL de {axis_es} no devolvió predicciones.")
    preds = np.asarray(preds).reshape(-1)
    if len(preds) != len(texts):
        raise PklClassifierError(
            f"El PKL de {axis_es} devolvió {len(preds)} predicciones para {len(texts)} textos."
        )
    return preds.tolist()


def classification_plan(
    ai_enabled: bool,
    tone_model=None,
    theme_model=None,
) -> Dict[str, bool]:
    """Describe qué eje usa IA existente vs PKL. El subtema nunca usa PKL."""
    has_tone = tone_model is not None
    has_theme = theme_model is not None
    return {
        "use_llm_tone": bool(ai_enabled) and not has_tone,
        "use_llm_theme": bool(ai_enabled) and not has_theme,
        "use_llm_subtema": bool(ai_enabled),
        "use_pkl_tone": has_tone,
        "use_pkl_theme": has_theme,
        "export_ai_columns": bool(ai_enabled) or has_tone or has_theme,
    }
