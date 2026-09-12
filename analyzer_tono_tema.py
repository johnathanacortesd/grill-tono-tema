# -*- coding: utf-8 -*-
"""Motor de Tono, Tema y Sub-tema (reemplaza el analisis de ai_analyzer.enrich_rows_with_ai).

CONTRATO (identico al motor anterior, para no tocar pipeline.py ni el formato de salida):
    entra -> rows (lista de dicts), km, brand, aliases, api_key, model, progress_callback,
             tone_model, theme_model, extra
    sale  -> los mismos rows con: 'Contexto analizado', 'Tono_IA', 'Tema_IA', 'Subtema_IA'
             (las filas duplicadas conservan 'Duplicada', '-', '-').

POR QUE ESTE MOTOR DA MEJOR RESULTADO QUE UN PROMPT SUELTO
  1. La etiqueta se decide por GRUPO de notas equivalentes, nunca fila por fila: dos notas
     iguales no pueden salir con tono distinto.
  2. Primero el SUB-TEMA (sintesis del hecho) y despues el TONO, con rubrica ordenada P1/P2/P3.
  3. VALIDADOR duro (3-7 palabras, sin verbo conjugado al inicio, sin terminar en preposicion,
     sin rotulos vacios) + ciclo de reparacion contra el propio modelo.
  4. El TEMA sale de una LISTA CERRADA de cubos del cliente por reglas lexicas; el modelo solo
     elige dentro de la lista o propone un cubo nuevo especifico. Nunca "Otros".
  5. Los sub-temas ya usados viajan en cada lote como CANDIDATOS: un mismo hecho reutiliza el
     mismo texto en vez de generar variantes.

Regla central del tono: el tema no decide el tono. Una nota triste o grave (desempleo, salud
mental, muertes, robos) NO es negativa para la marca; Negativo exige critica, denuncia o
señalamiento DIRIGIDO a la marca o a su vocero.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import requests

from catalogo_tono_tema import (
    CRITERIOS_TONO, CUBO_PROHIBIDO, EJEMPLOS, EJEMPLOS_SECTOR, EJEMPLOS_TEMA, MAX_PAL, META_CUBO,
    MIN_PAL, REGLAS_SUBTEMA, TONOS, taxonomia_por_nombre,
)


def _contexto_marca(texto: str, titulo: str, brand: str, aliases: Sequence[str]) -> str:
    """Recorte alrededor de la mencion de la marca, para la columna 'Contexto analizado'.

    Usa las funciones del motor anterior (ai_analyzer) cuando estan disponibles; si no, cae a un
    recorte simple. Asi el motor de tono/tema no depende del paquete `openai` para funcionar.
    """
    try:
        from ai_analyzer import extract_brand_context, generate_brand_variants
        regexes = generate_brand_variants(brand, aliases)
        return extract_brand_context(texto, titulo, regexes)
    except Exception:
        return sq('%s %s' % (titulo, texto))[:300]

BASE_URL_DEFECTO = "https://api.openai.com/v1"
MODELO_DEFECTO = "gpt-4.1-nano-2025-04-14"
TAM_LOTE_DEFECTO = 10
WORKERS_DEFECTO = 4
UMBRAL_TITULO_DEFECTO = 92
UMBRAL_CUERPO_DEFECTO = 85
K_BODY, MIN_GRAMAS, MIN_PALABRAS_TITULO = 5, 30, 3

_ULTIMO_RESUMEN: Dict[str, object] = {}


def ultimo_resumen() -> Dict[str, object]:
    """Estadisticas de la ultima corrida (la interfaz las muestra al terminar)."""
    return dict(_ULTIMO_RESUMEN)


# ============================================================================
# 1. Utilidades de texto
# ============================================================================
def ctrl(s) -> str:
    return ''.join(ch for ch in str(s or '') if (ch >= ' ' or ch in '\n\t') and ch not in '\ufffe\uffff')


def nz(s) -> str:
    s = unicodedata.normalize('NFKD', ctrl(s))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9ñ ]+', ' ', s)).strip()


def words(s) -> List[str]:
    s = unicodedata.normalize('NFKD', ctrl(s))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    return re.findall(r'[a-z0-9ñ]+', s)


def grams(w: List[str], k: int) -> set:
    return set(tuple(w[i:i + k]) for i in range(max(0, len(w) - k + 1)))


def raiz(t: str) -> str:
    t = nz(t)
    if len(t) > 4 and t.endswith('es'):
        return t[:-2]
    if len(t) > 3 and t.endswith('s'):
        return t[:-1]
    return t


def sq(s) -> str:
    return re.sub(r'\s+', ' ', ctrl(s)).strip()


GENERIC_TITULO = set("""a al algo algunos ante antes aqui asi aun aunque bien cada como con contra cual cuando
de del desde donde dos el ella ellas ellos en entre era eran es esa esas ese eso esos esta estaba
estan este esto estos fue fueron ha hace hacia hasta hay la las le le los lo los mas me mi mis
mucho muy nos o os otra otras otro otros para pero poco por porque que quien se sea segun ser si
sin sobre son su sus tal tambien tan tanto te tiene tienen todo todos tu tus un una uno unos y ya""".split())


# ============================================================================
# 2. Grupo de notas equivalentes (republicaciones y duplicados de contenido)
# ============================================================================
def _texto_fila(row: dict, km: dict) -> str:
    return str(row.get('Resumen - Aclaracion') or row.get('resumen corto') or row.get('Resumen') or '')


def _titulo_fila(row: dict, km: dict) -> str:
    return str(row.get(km.get('titulo', 'Título')) or row.get('Título') or '')


def construir_grupos(
    rows: List[dict],
    km: dict,
    umbral_titulo: int = UMBRAL_TITULO_DEFECTO,
    umbral_cuerpo: int = UMBRAL_CUERPO_DEFECTO,
) -> Tuple[List[dict], Dict[int, int]]:
    """Agrupa filas no duplicadas por similitud de titulo (palabras de contenido) y de resumen.

    Devuelve (grupos, mapa_indice_fila -> id de grupo). Las filas 'is_duplicate' se excluyen:
    heredan la etiqueta de su original por 'ID duplicada' en el flujo de limpieza.
    """
    from rapidfuzz import fuzz, process

    idx_validos = [i for i, r in enumerate(rows) if not r.get('is_duplicate')]
    if not idx_validos:
        return [], {}

    base = []
    for i in idx_validos:
        tit = _titulo_fila(rows[i], km)
        txt = _texto_fila(rows[i], km)
        base.append({
            'idx': i,
            'titulo': sq(tit),
            'texto': sq(txt),
            'ctit': set(w for w in words(tit) if w not in GENERIC_TITULO),
            'g5': grams(words(txt), K_BODY),
        })

    par = list(range(len(base)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    def uni(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[max(ra, rb)] = min(ra, rb)

    tit = [' '.join(sorted(b['ctit'])) for b in base]
    if len(base) > 1:
        t1 = process.cdist(tit, tit, scorer=fuzz.ratio, workers=-1) / 100.0
        t2 = process.cdist(tit, tit, scorer=fuzz.token_sort_ratio, workers=-1) / 100.0
        import numpy as np
        T = np.maximum(t1, t2)
        for i in range(len(base)):
            for j in np.where(T[i] >= umbral_titulo / 100.0)[0]:
                if j > i and len(base[i]['ctit'] & base[j]['ctit']) >= MIN_PALABRAS_TITULO:
                    uni(i, j)

    inv = defaultdict(set)
    for j, b in enumerate(base):
        for g in b['g5']:
            inv[g].add(j)
    for i, b in enumerate(base):
        if len(b['g5']) < MIN_GRAMAS:
            continue
        hits = Counter()
        for g in b['g5']:
            for j in inv.get(g, ()):
                if j != i:
                    hits[j] += 1
        for j, inter in hits.items():
            if j > i and min(len(b['g5']), len(base[j]['g5'])) >= MIN_GRAMAS and \
                    inter / min(len(b['g5']), len(base[j]['g5'])) >= umbral_cuerpo / 100.0:
                uni(i, j)

    por_raiz = defaultdict(list)
    for k in range(len(base)):
        por_raiz[find(k)].append(k)

    grupos, mapa = [], {}
    for gid, miembros in enumerate(sorted(por_raiz.values(), key=lambda v: -len(v)), 1):
        idxs = [base[k]['idx'] for k in miembros]
        reps = Counter(base[k]['titulo'] for k in miembros)
        rep = reps.most_common(1)[0][0] or base[miembros[0]]['texto'][:120]
        cuerpo = max((base[k]['texto'] for k in miembros), key=len)
        alt = [t for t in sorted(set(base[k]['titulo'] for k in miembros)) if t and t != rep][:3]
        grupos.append({'grupo': gid, 'n': len(idxs), 'idxs': idxs, 'titulo': rep,
                       'titulos_alt': alt, 'texto': cuerpo[:900]})
        for i in idxs:
            mapa[i] = gid
    return grupos, mapa


# ============================================================================
# 3. Validador de etiquetas
# ============================================================================
PREP_FIN = {'de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'unos', 'unas', 'para', 'en', 'con',
            'por', 'y', 'o', 'a', 'al', 'que', 'su', 'sus', 'sin', 'sobre', 'entre', 'tras', 'ni'}
CONECT = PREP_FIN | {'se', 'lo', 'le', 'les', 'es', 'son', 'como', 'mas', 'más', 'muy'}
VERBOS1 = set("""entregan anuncian avanza avanzan instalan reconocen firman inauguran denuncian alertan
piden exigen rechazan critican senalan señalan aseguran confirman advierten solicitan denunciaron
anunciaron instalaron avanzaron reconocieron inauguraron entregaron logran obtienen reciben presentan
lideran realizan adelantan ejecutan mejoran aumentan disminuyen reducen destinan aprueban celebran
conmemoran rinden posesionan nombran designan ratifican reafirman garantizan benefician participan
visitan recorren supervisan verifican socializan capacitan forman graduan certifican arranca culmina
inicia termina sigue siguen mantiene mantienen trabaja trabajan llevan deja dejan abre abren obtiene
recibe recibio recibieron pidieron exigieron superviso entrego anuncio advirtio aseguro confirmo
denuncio critico lidero presento aprobo celebro conmemoro designo nombro""".split())
RE_VERBO = re.compile(r'(aron|ieron|ió|eó|arán|erán|irán|aba|aban|amos|imos)$')
ROTULO_GEN = {
    'gestion gubernamental', 'gestion institucional', 'gestion departamental', 'actividad institucional',
    'actividad gubernamental', 'noticias de la entidad', 'noticias generales', 'temas generales',
    'cobertura informativa', 'panorama regional', 'informacion general', 'actualidad departamental',
    'eventos institucionales', 'otros', 'varios', 'general', 'miscelaneo', 'miscelanea',
}
MARCO = {'noticias', 'informacion', 'información', 'cobertura', 'actualidad', 'eventos', 'actividades',
         'destacados', 'panorama', 'menciones', 'informe'}
FILLER = MARCO | {'importantes', 'relevantes', 'generales', 'varias', 'diversos', 'diversas',
                  'departamental', 'institucional', 'gubernamental', 'regional', 'recientes', 'varios'}


def validar(sub_tema, tono, fuentes, min_pal=MIN_PAL, max_pal=MAX_PAL) -> List[str]:
    """Problemas encontrados. Lista vacia = etiqueta valida. Los avisos 'revisar_anclaje' son blandos."""
    p = []
    sub_tema = str(sub_tema or '').strip()
    if not sub_tema:
        return ['vacio']
    if re.search(r'[:;|"\'«»—–]', sub_tema):
        p.append('caracter_marcador')
    w = sub_tema.split()
    if len(w) < min_pal:
        p.append('corto(%d)' % len(w))
    if len(w) > max_pal:
        p.append('largo(%d)' % len(w))
    if nz(w[-1]) in PREP_FIN:
        p.append('termina_preposicion')
    prim = nz(w[0])
    nexo2 = len(w) > 1 and nz(w[1]) in PREP_FIN
    if not nexo2 and (prim in VERBOS1 or (len(prim) > 4 and RE_VERBO.search(prim))):
        p.append('verbo_inicial(%s)' % prim)
    if nz(sub_tema) in ROTULO_GEN:
        p.append('rotulo_generico')
    toks = [nz(t) for t in w]
    if toks and toks[0] in MARCO and all(t in FILLER for t in toks[1:]):
        p.append('marco_vacio')
    if tono not in TONOS:
        p.append('tono_invalido(%s)' % tono)
    fuente = ' '.join(nz(f) for f in (fuentes or []))
    ft = set(re.findall(r'[a-z0-9ñ]+', fuente))
    fr = {raiz(t) for t in ft}
    faltan = [t for t in toks if len(t) >= 4 and t not in CONECT and t not in ft and raiz(t) not in ft]
    if len(faltan) > 1:
        p.append('revisar_anclaje(%s)' % ','.join(faltan[:4]))
    return p


# ============================================================================
# 4. Taxonomia de Temas (lista cerrada + propuesta de cubo nuevo especifico)
# ============================================================================
def patron(kw: str) -> str:
    if '(' in kw or '?' in kw:
        return r'(?<![a-z])' + kw
    if kw.endswith('*'):
        return r'(?<![a-z])' + re.escape(nz(kw[:-1])) + r'[a-z]*'
    return r'(?<![a-z])' + re.escape(nz(kw)) + r'(?![a-z])'


def tema_de(sub_tema: str, titulo: str, tax: dict):
    """Dos pasadas: manda el sub-tema (sintesis limpia); el titulo solo si parece titular corto."""
    for txt in (nz(sub_tema), nz(titulo) if len(str(titulo or '')) <= 160 else ''):
        if not txt:
            continue
        for r in tax['reglas']:
            for k in r['claves']:
                if re.search(patron(k), txt):
                    return r['tema'], k
    return None, None


def cubo_valido(nombre, tax, permitir_nuevos=True):
    nombre = sq(nombre)
    if not nombre:
        return None
    n = nz(nombre)
    if n in CUBO_PROHIBIDO or n in ROTULO_GEN:
        return None
    en_lista = next((t for t in tax['temas'] if nz(t) == n), None)
    if en_lista:
        return en_lista
    if not permitir_nuevos or not (2 <= len(nombre.split()) <= 5):
        return None
    toks = [t for t in n.split() if t]
    if any(t in META_CUBO for t in toks):
        return None
    contenido = [t for t in toks if t not in CONECT and t not in FILLER and t not in MARCO and len(t) > 3]
    return nombre if contenido else None


def _cubo_mas_cercano(sub_tema: str, titulo: str, tax: dict) -> str:
    """Fallback determinista: el cubo con mas tokens en comun. Nunca devuelve 'Otros'."""
    objetivo = set(re.findall(r'[a-z0-9ñ]+', nz('%s %s' % (sub_tema, titulo))))
    mejor, score = None, -1
    for t in tax['temas']:
        if nz(t) in CUBO_PROHIBIDO:
            continue
        claves = set(re.findall(r'[a-z0-9ñ]+', nz(t)))
        s = len(objetivo & claves)
        if s > score:
            mejor, score = t, s
    return mejor or tax['temas'][0]


# ============================================================================
# 5. Prompts (rubrica ordenada + ejemplos + contrato JSON)
# ============================================================================
def prompt_sistema(cfg: dict) -> str:
    crit = cfg.get('criterio') or list(CRITERIOS_TONO)[0]
    regla = CRITERIOS_TONO.get(crit) or list(CRITERIOS_TONO.values())[0]
    lineas = [
        'Eres analista senior de monitoreo de medios en Colombia. Etiquetas cada GRUPO de notas',
        '(una nota publicada por varios medios = un grupo) y devuelves JSON.',
        '',
        'MARCA / ENTIDAD OBJETIVO: %s' % (cfg.get('brand') or 'la entidad'),
        'VOCERO(S): %s' % (', '.join(cfg.get('voceros') or []) or 'no definido'),
        'ALIAS Y FORMAS DE NOMBRARLA: %s' % (', '.join(cfg.get('aliases') or []) or 'ninguno'),
        '',
        'REGLA DE TONO',
        regla,
        '',
        'REGLA DE SUB-TEMA',
        REGLAS_SUBTEMA,
        '',
        'EJEMPLOS YA ETIQUETADOS (imita el criterio, la brevedad y las mayusculas)',
    ]
    ejemplos = list(EJEMPLOS) + EJEMPLOS_TEMA
    if crit.startswith('Favorabilidad'):
        ejemplos += EJEMPLOS_SECTOR
    for e in ejemplos:
        lineas.append('  TITULAR: %s' % e['titulo'])
        lineas.append('  ->  sub_tema: "%s"  |  tono: %s' % (e['sub_tema'], e['tono']))
    lineas += [
        '',
        'SALIDA: solo JSON, sin markdown y sin explicaciones:',
        '{"resultados":[{"id":<numero de grupo>,"sub_tema":"<3 a 5 palabras>",'
        '"tono":"Positivo|Neutro|Negativo"}]}',
        'Un objeto por cada grupo recibido, con su id exacto.',
    ]
    return '\n'.join(lineas)


def prompt_lote(grupos_lote: Sequence[dict], candidatos: Sequence[str]) -> str:
    bloques = []
    for g in grupos_lote:
        b = ['GRUPO id=%d (%d menciones)' % (g['grupo'], g['n']),
             'TITULAR: %s' % sq(g['titulo'])[:220]]
        if g.get('titulos_alt'):
            b.append('OTROS TITULARES DEL MISMO GRUPO: %s'
                     % ' // '.join(sq(t)[:120] for t in g['titulos_alt']))
        b.append('TEXTO: %s' % sq(g['texto'])[:900])
        bloques.append('\n'.join(b))
    msg = '\n\n'.join(bloques)
    msg += '\n\nRecuerda: el sub_tema de cada grupo debe tener entre 3 y 5 palabras, y solo JSON.'
    if candidatos:
        msg += ('\n\nCANDIDATOS (sub-temas ya usados; reutiliza el texto exacto si es el mismo hecho):\n'
                + '\n'.join('- %s' % c for c in list(candidatos)[-120:]))
    return msg


def prompt_reparacion(fallos: Sequence[dict]) -> str:
    detalle = []
    for f in fallos:
        detalle.append('GRUPO id=%d\nTITULAR: %s\nTEXTO: %s\nSUB-TEMA ACTUAL: "%s"\nPROBLEMAS: %s'
                       % (f['grupo'], sq(f['titulo'])[:180], sq(f['texto'])[:450],
                          f['sub_tema'], '; '.join(f['problemas'])))
    return ('Corrige SOLO estos sub-temas. Devuelve el mismo tono salvo que el tono no sea valido.\n'
            'Un sub-tema valido tiene 3 a 5 palabras (maximo 7) en frase nominal, no empieza con verbo\n'
            'conjugado, no termina en preposicion y no lleva marcadores ni rotulos vacios. Si el problema\n'
            'dice largo(N), recorta a 5 palabras sin perder el hecho.\n\n'
            + '\n\n'.join(detalle)
            + '\n\nResponde UNICAMENTE con {"resultados":[{"id":<grupo>,"sub_tema":"...","tono":"..."}]}')


def prompt_cubos(pendientes: Sequence[dict], tax: dict, permitir_nuevos: bool) -> str:
    lista = '\n'.join('- %s' % t for t in tax['temas'] if nz(t) not in CUBO_PROHIBIDO)
    extra = ('Si ningun cubo sirve, propón uno NUEVO en 2 a 5 palabras que describa el asunto concreto\n'
             '(por ejemplo "Tramite de pasaportes"). No se acepta un cubo generico.\n'
             if permitir_nuevos else 'No propongas cubos nuevos: elige siempre uno de la lista.\n')
    bloques = ['GRUPO id=%d\nSUB-TEMA: %s\nTITULAR: %s' % (p['grupo'], p['sub_tema'], sq(p['titulo'])[:180])
               for p in pendientes]
    return ('Clasificas notas de prensa en cubos tematicos cerrados.\nCubos disponibles:\n%s\n\n%s'
            'Responde UNICAMENTE con {"resultados":[{"id":<grupo>,"cubo":"<nombre del cubo>"}]}\n\n%s'
            % (lista, extra, '\n\n'.join(bloques)))


# ============================================================================
# 6. Capa LLM
# ============================================================================
def _json_loose(txt):
    txt = re.sub(r'^```(?:json)?|```$', '', str(txt or '').strip(), flags=re.M).strip()
    try:
        return json.loads(txt)
    except Exception:
        pass
    m = re.search(r'\{.*\}', txt, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None
    return None


def llamar_llm(cfg: dict, mensajes: List[dict], json_mode: bool = True,
               max_tokens: int = 4000, temperatura: float = 0.0, intentos: int = 3) -> str:
    url = (cfg.get('base_url') or BASE_URL_DEFECTO).rstrip('/') + '/chat/completions'
    payload = {'model': cfg.get('model') or MODELO_DEFECTO, 'messages': mensajes,
               'temperature': temperatura, 'max_tokens': max_tokens}
    if json_mode:
        payload['response_format'] = {'type': 'json_object'}
    cab = {'Authorization': 'Bearer %s' % cfg.get('api_key', ''), 'Content-Type': 'application/json'}
    ultimo = ''
    for k in range(intentos):
        try:
            r = requests.post(url, headers=cab, json=payload, timeout=cfg.get('timeout', 120))
            if r.status_code in (429, 500, 502, 503):
                ultimo = 'HTTP %s' % r.status_code
                time.sleep(2 + 3 * k)
                continue
            if r.status_code != 200:
                raise RuntimeError('HTTP %s: %s' % (r.status_code, r.text[:300]))
            return r.json()['choices'][0]['message']['content']
        except requests.RequestException as e:
            ultimo = str(e)[:200]
            time.sleep(2 + 3 * k)
    raise RuntimeError('Fallo la llamada al modelo: %s' % ultimo)


def _normaliza_label(d: dict, ids_lote: Sequence[int]) -> Dict[int, dict]:
    salida = {}
    for r in (d or {}).get('resultados', []) or []:
        try:
            gid = int(r.get('id'))
        except Exception:
            continue
        if gid in ids_lote:
            tono = sq(r.get('tono')).capitalize()
            salida[gid] = {'sub_tema': sq(r.get('sub_tema')),
                           'tono': tono if tono in TONOS else 'Neutro'}
    return salida


def _voto_mayoria(por_grupo: List[Dict[int, dict]], ids_lote: Sequence[int]) -> Dict[int, dict]:
    """Combina las pasadas de votacion: gana el tono mas votado (empate -> Neutro) y el sub-tema
    mas repetido (empate -> el mas corto). Reduce el ruido de los modelos pequenos en los casos
    limite: si una nota sale Negativa en una pasada y Neutra en otra, queda Neutra."""
    salida = {}
    for gid in ids_lote:
        tonos = [v[gid]['tono'] for v in por_grupo if gid in v and v[gid].get('tono')]
        subs = [v[gid]['sub_tema'] for v in por_grupo if gid in v and v[gid].get('sub_tema')]
        if not tonos and not subs:
            continue
        c = Counter(tonos)
        top = c.most_common()
        if not top:
            tono = 'Neutro'
        elif len(top) > 1 and top[0][1] == top[1][1]:
            tono = 'Neutro' if 'Neutro' in [top[0][0], top[1][0]] else top[0][0]
        else:
            tono = top[0][0]
        cs = Counter(nz(s) for s in subs)
        if not cs:
            sub = ''
        else:
            maxrep = max(cs.values())
            candidatos = [s for s in subs if cs[nz(s)] == maxrep]
            sub = min(candidatos, key=len)
        salida[gid] = {'sub_tema': sub, 'tono': tono}
    return salida


def etiquetar_grupos(cfg: dict, grupos: List[dict], progress: Optional[Callable] = None,
                     tam_lote: int = TAM_LOTE_DEFECTO, workers: int = WORKERS_DEFECTO,
                     max_reparaciones: int = 2, votos: int = 2) -> Dict[int, dict]:
    """Etiqueta todos los grupos: lotes en paralelo -> votacion -> validacion -> reparacion.

    Con `votos=2` cada lote se etiqueta dos veces y se toma la mayoria: los casos limite dejan de
    bailar entre corridas (un empate en el tono cae a Neutro, que es la regla de prudencia).
    La canonizacion de sub-temas se hace despues, de forma determinista, porque los lotes corren
    en paralelo y no ven las etiquetas de los demas mientras trabajan.
    """
    if not grupos:
        return {}
    votos = max(1, int(votos))
    lotes = [grupos[i:i + tam_lote] for i in range(0, len(grupos), tam_lote)]
    etiquetas: Dict[int, dict] = {}
    fallidos: List[int] = []
    hechos = [0]

    def trabajo(lote):
        ids = [g['grupo'] for g in lote]
        sys_msg = [{'role': 'system', 'content': prompt_sistema(cfg)},
                   {'role': 'user', 'content': prompt_lote(lote, [])}]
        for intento in range(2):
            try:
                txt = llamar_llm(cfg, sys_msg)
                labels = _normaliza_label(_json_loose(txt), ids)
                if labels:
                    return lote, labels
            except Exception:
                if intento == 1:
                    raise
                time.sleep(2)
        return lote, {}

    resultados = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
        futuros = {}
        for lote in lotes:
            for _v in range(votos):
                futuros[ex.submit(trabajo, lote)] = lote
        for fut in as_completed(futuros):
            lote = futuros[fut]
            try:
                resultados.append(fut.result())
            except Exception as e:
                resultados.append((lote, {'__error__': str(e)[:200]}))
            hechos[0] += len(lote)
            if progress and hechos[0] % max(1, len(lotes)) == 0:
                avance = min(1.0, hechos[0] / max(1, len(grupos) * votos))
                progress(min(92, 70 + int(18 * avance)),
                         'Analizando con IA… %d/%d grupos%s'
                         % (min(hechos[0], len(grupos) * votos), len(grupos) * votos,
                            ' (doble verificación)' if votos > 1 else ''))

    con_error = []
    if votos > 1:
        por_lote: Dict[int, List[Dict[int, dict]]] = defaultdict(list)
        for lote, labels in resultados:
            if '__error__' in labels:
                con_error.append(labels['__error__'])
                continue
            por_lote[lote[0]['grupo']].append(labels)
        for lote in lotes:
            comb = _voto_mayoria(por_lote.get(lote[0]['grupo'], []), [g['grupo'] for g in lote])
            for g in lote:
                etiquetas[g['grupo']] = comb.get(g['grupo'], {'sub_tema': '', 'tono': ''})
    else:
        for lote, labels in resultados:
            if '__error__' in labels:
                con_error.append(labels['__error__'])
                labels = {}
            for g in lote:
                etiquetas[g['grupo']] = labels.get(g['grupo'], {'sub_tema': '', 'tono': ''})

    # ---- reparacion secuencial de etiquetas invalidas (segunda vuelta al modelo) ----
    por_grupo = {g['grupo']: g for g in grupos}
    for ronda in range(max_reparaciones):
        fallos = []
        for g in grupos:
            e = etiquetas[g['grupo']]
            pr = validar(e['sub_tema'], e['tono'],
                         [g['titulo']] + g.get('titulos_alt', []) + [g['texto']])
            duros = [x for x in pr if not x.startswith('revisar_anclaje')]
            if duros or not e['sub_tema']:
                fallos.append({'grupo': g['grupo'], 'titulo': g['titulo'], 'texto': g['texto'],
                               'sub_tema': e['sub_tema'], 'problemas': duros or ['vacio']})
        if not fallos:
            break
        if progress:
            progress(min(93, 92), 'Reparando %d etiquetas…' % len(fallos))
        for i in range(0, len(fallos), 12):
            trozo = fallos[i:i + 12]
            try:
                txt = llamar_llm(cfg, [{'role': 'system', 'content': prompt_sistema(cfg)},
                                       {'role': 'user', 'content': prompt_reparacion(trozo)}])
                corr = _normaliza_label(_json_loose(txt), [f['grupo'] for f in trozo])
            except Exception:
                corr = {}
            for gid, v in corr.items():
                if v.get('sub_tema'):
                    etiquetas[gid] = v

    # ---- fallback determinista para lo que quedo vacio: nunca dejamos una fila sin etiqueta ----
    for g in grupos:
        e = etiquetas[g['grupo']]
        if not e.get('sub_tema'):
            palabras = [w for w in words(g['titulo']) if w not in GENERIC_TITULO][:5]
            e['sub_tema'] = ' '.join(palabras).capitalize() if palabras else 'Hecho informativo'
            fallidos.append(g['grupo'])
        if not e.get('tono'):
            e['tono'] = 'Neutro'

    _ULTIMO_RESUMEN['grupos'] = len(grupos)
    _ULTIMO_RESUMEN['errores_api'] = con_error[:5]
    _ULTIMO_RESUMEN['grupos_con_fallback'] = fallidos
    return etiquetas


def canonizar_subtemas(etiquetas: Dict[int, dict], umbral: float = 0.86) -> int:
    """Unifica variantes del mismo sub-tema: deja el texto mas frecuente (y mas corto si empatan).

    Es la version determinista de la canonizacion: en lotes paralelos el modelo no ve las
    etiquetas de los demas lotes, asi que aqui se juntan las variantes equivalentes.
    """
    from rapidfuzz import fuzz
    conteo = Counter(nz(e['sub_tema']) for e in etiquetas.values() if e.get('sub_tema'))
    if len(conteo) <= 1:
        return 0
    grupos, canon, cambios = [], {}, 0
    for texto, n in conteo.most_common():
        destino = None
        for rep in grupos:
            if fuzz.token_sort_ratio(texto, rep) >= umbral * 100:
                destino = rep
                break
        if destino is None:
            grupos.append(texto)
            canon[texto] = (texto, n)
        else:
            canon[texto] = (destino, n)
    for e in etiquetas.values():
        k = nz(e.get('sub_tema'))
        if k in canon and canon[k][0] != k:
            original = e['sub_tema']
            mejor = max((t for t in etiquetas.values() if nz(t.get('sub_tema')) == canon[k][0]),
                        key=lambda x: len(x['sub_tema']), default=None)
            if mejor is not None:
                e['sub_tema'] = mejor['sub_tema']
                if nz(e['sub_tema']) != nz(original):
                    cambios += 1
    return cambios


def elegir_cubos(cfg: dict, pendientes: Sequence[dict], tax: dict,
                 permitir_nuevos: bool = True) -> Dict[int, str]:
    """El modelo elige dentro de la lista cerrada (o propone un cubo nuevo especifico)."""
    out: Dict[int, str] = {}
    if not pendientes:
        return out
    try:
        txt = llamar_llm(cfg, [{'role': 'system',
                                'content': 'Clasificas notas en cubos tematicos cerrados. Respondes en JSON.'},
                               {'role': 'user', 'content': prompt_cubos(pendientes, tax, permitir_nuevos)}])
        data = _json_loose(txt) or {}
    except Exception:
        data = {}
    for r in data.get('resultados', []) or []:
        try:
            gid = int(r.get('id'))
        except Exception:
            continue
        c = cubo_valido(r.get('cubo'), tax, permitir_nuevos)
        if c:
            out[gid] = c
    return out


# ============================================================================
# 7. Asignacion final de Tema
# ============================================================================
def _mismo_cubo(a: str, b: str) -> bool:
    """Dos nombres de cubo son el mismo si son casi iguales o si uno es el otro con un añadido.

    Caso real: 'Prevencion del suicidio' y 'Prevencion del suicidio en Barranquilla' son el mismo
    cubo, y la similitud por token_sort no llega al umbral porque la segunda agrega palabras.
    """
    from rapidfuzz import fuzz
    if fuzz.token_sort_ratio(nz(a), nz(b)) >= 90:
        return True
    ta, tb = set(nz(a).split()), set(nz(b).split())
    chico, grande = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    return chico <= grande and len(chico) >= 2 and 0 < len(grande) - len(chico) <= 3


def canonizar_cubos(temas: Dict[int, str], tax: dict) -> int:
    """Unifica cubos NUEVOS que son variantes del mismo nombre. Los de la lista del cliente no se tocan."""
    en_lista = {nz(t) for t in tax['temas']}
    conteo = Counter(t for t in temas.values() if nz(t) not in en_lista)
    if len(conteo) <= 1:
        return 0
    reps, canon = [], {}
    for nombre, _n in conteo.most_common():
        destino = next((r for r in reps if _mismo_cubo(nombre, r)), None)
        if destino is None:
            reps.append(nombre)
            canon[nombre] = nombre
        else:
            canon[nombre] = destino
    cambios = 0
    for k, v in list(temas.items()):
        nuevo = canon.get(v, v)
        if nz(nuevo) != nz(v):
            temas[k] = nuevo
            cambios += 1
    return cambios


def derivar_reglas(cubos: Sequence[str]) -> List[dict]:
    """Convierte una lista de cubos en reglas lexicas para el primer pase determinista.

    Cada cubo aporta su nombre completo y sus palabras de contenido como claves exactas. Las reglas
    se ordenan del cubo mas especifico (mas palabras) al mas general, para que gane el que mas
    describe el hecho.
    """
    reglas = []
    for nombre in cubos:
        toks = [t for t in nz(nombre).split() if t]
        claves = [nz(nombre)]
        for t in toks:
            if len(t) >= 4 and t not in CONECT and t not in FILLER and t not in MARCO and t not in claves:
                claves.append(t)
        if len(claves) > 1:
            reglas.append({'tema': nombre, 'claves': claves})
    reglas.sort(key=lambda r: -len(nz(r['tema']).split()))
    return reglas


def _muestreo_grupos(grupos: Sequence[dict], etiquetas: Dict[int, dict], por_bloque: int = 35,
                     max_bloques: int = 12) -> List[List[str]]:
    lineas = []
    for g in grupos:
        st_ = (etiquetas.get(g['grupo']) or {}).get('sub_tema') or ''
        lineas.append('- %s | %s' % (st_[:60], sq(g['titulo'])[:110]))
    if len(lineas) > por_bloque * max_bloques:
        paso = max(1, len(lineas) // (por_bloque * max_bloques))
        lineas = lineas[::paso]
    return [lineas[i:i + por_bloque] for i in range(0, len(lineas), por_bloque)]


def proponer_taxonomia(cfg: dict, grupos: List[dict], etiquetas: Dict[int, dict],
                       objetivo: int = 16, progress: Optional[Callable] = None) -> dict:
    """Construye la lista de Temas A PARTIR DEL CONTENIDO del archivo, sin lista fija.

    Los clientes son muy distintos (universidades, sector publico, privado, marcas), asi que los
    cubos se proponen leyendo los hechos del propio dossier: primero por bloques y despues con una
    consolidacion que elimina duplicados y solapamientos.
    """
    if progress:
        progress(93, 'Proponiendo la lista de Temas a partir del archivo…')
    bloques = _muestreo_grupos(grupos, etiquetas)
    propuestas: List[str] = []
    for bloque in bloques:
        msgs = [{'role': 'system', 'content':
                 'Eres analista de medios en Colombia. Agrupas hechos en cubos tematicos. Respondes en JSON.'},
                {'role': 'user', 'content':
                 'Estos son hechos de un dossier de prensa:\n\n' + '\n'.join(bloque) +
                 '\n\nPropón entre 10 y 14 CUBOS TEMATICOS que los agrupen, pensando en un cliente '
                 'colombiano (puede ser universidad, entidad publica, empresa privada o marca).\n'
                 'Reglas: nombres de 2 a 5 palabras; especificos de ESTOS hechos, no genericos; sin '
                 'solaparse entre si; sin contar el nombre de la marca; nada de "Otros", "Varios", '
                 '"General" ni "Informacion".\n'
                 'Responde solo JSON: {"cubos":["Cubo uno","Cubo dos"]}'}]
        try:
            data = _json_loose(llamar_llm(cfg, msgs)) or {}
        except Exception:
            data = {}
        for c in data.get('cubos', []) or []:
            v = cubo_valido(c, {'temas': propuestas}, permitir_nuevos=True)
            if v and not any(_mismo_cubo(v, p) for p in propuestas):
                propuestas.append(v)

    if not propuestas:
        return taxonomia_por_nombre('Gobierno territorial')

    # --- consolidacion final: una sola lista sin solapamientos ---
    msgs = [{'role': 'system', 'content':
             'Eres analista de medios en Colombia. Consolidas listas de cubos tematicos en JSON.'},
            {'role': 'user', 'content':
             'Estos cubos fueron propuestos por varios analistas para el mismo dossier:\n\n'
             + '\n'.join('- %s' % p for p in propuestas) +
             '\n\nDevuelve la LISTA FINAL de %d cubos (puede ser menos si no hay materia): sin '
             'duplicados, sin solaparse, de 2 a 5 palabras, especificos, y sin "Otros" ni genericos.\n'
             'Responde solo JSON: {"cubos":["..."]}' % objetivo}]
    try:
        data = _json_loose(llamar_llm(cfg, msgs)) or {}
    except Exception:
        data = {}
    finales: List[str] = []
    for c in data.get('cubos', []) or propuestas:
        if not isinstance(c, str):
            continue
        v = cubo_valido(c, {'temas': finales}, permitir_nuevos=True)
        if v and not any(_mismo_cubo(v, f) for f in finales):
            finales.append(v)
    if len(finales) < 3:
        finales = propuestas[:max(3, objetivo)]
    tax = {'nota': 'Cubos generados automaticamente a partir del contenido de este archivo.',
           'temas': finales, 'reglas': derivar_reglas(finales)}
    if progress:
        progress(94, 'Lista de Temas generada: %d cubos' % len(finales))
    return tax


def asignar_temas(cfg: dict, grupos: List[dict], etiquetas: Dict[int, dict], tax: dict,
                  progress: Optional[Callable] = None) -> Tuple[Dict[int, str], Dict[int, str]]:
    temas, origen, pendientes = {}, {}, []
    for g in grupos:
        e = etiquetas.get(g['grupo'], {})
        t, k = tema_de(e.get('sub_tema', ''), g['titulo'], tax)
        if t:
            temas[g['grupo']] = t
            origen[g['grupo']] = 'regla:%s' % k
        else:
            pendientes.append({'grupo': g['grupo'], 'sub_tema': e.get('sub_tema', ''),
                               'titulo': g['titulo']})
    if pendientes and progress:
        progress(min(93, 93), 'Clasificando tema de %d grupos nuevos…' % len(pendientes))
    elegidos = elegir_cubos(cfg, pendientes, tax, permitir_nuevos=True)
    nuevos = []
    for p in pendientes:
        t = elegidos.get(p['grupo'])
        if not t:
            t = _cubo_mas_cercano(p['sub_tema'], p['titulo'], tax)
            origen[p['grupo']] = 'cercano'
        else:
            origen[p['grupo']] = 'llm'
            if nz(t) not in {nz(x) for x in tax['temas']}:
                nuevos.append(t)
        temas[p['grupo']] = t
    _ULTIMO_RESUMEN['cubos_nuevos'] = sorted(set(nuevos))
    _ULTIMO_RESUMEN['temas_por_llm'] = sum(1 for v in origen.values() if v == 'llm')
    _ULTIMO_RESUMEN['temas_por_regla'] = sum(1 for v in origen.values() if v.startswith('regla'))
    unificados = canonizar_cubos(temas, tax)
    if unificados:
        _ULTIMO_RESUMEN['cubos_unificados'] = unificados
        _ULTIMO_RESUMEN['cubos_nuevos'] = sorted(set(temas.values()) - {t for t in tax['temas']})
    return temas, origen


# ============================================================================
# 8. Entrada compatible con el pipeline
# ============================================================================
def enrich_rows_with_ai(
    rows: List[dict],
    km: dict,
    brand: str,
    aliases: List[str],
    api_key: str,
    model: str = MODELO_DEFECTO,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    tone_model=None,
    theme_model=None,
    extra: Optional[dict] = None,
) -> List[dict]:
    """Llena 'Contexto analizado', 'Tono_IA', 'Tema_IA' y 'Subtema_IA' con el motor de tono/tema/subtema."""
    extra = dict(extra or {})
    cfg = {
        'brand': brand,
        'aliases': list(aliases or []),
        'voceros': list(extra.get('voceros') or []),
        'criterio': extra.get('criterio') or list(CRITERIOS_TONO)[0],
        'api_key': api_key,
        'model': model or MODELO_DEFECTO,
        'base_url': extra.get('base_url') or BASE_URL_DEFECTO,
        'timeout': int(extra.get('timeout', 120)),
    }
    modo_tax = extra.get('taxonomia')
    tax = None
    if isinstance(modo_tax, dict):
        tax = modo_tax
    elif not modo_tax or str(modo_tax).lower().startswith('autom'):
        tax = None  # se genera despues de etiquetar, con los hechos de este archivo
    else:
        tax = taxonomia_por_nombre(modo_tax)
    tam_lote = int(extra.get('tam_lote') or TAM_LOTE_DEFECTO)
    workers = int(extra.get('workers') or WORKERS_DEFECTO)
    votos = int(extra.get('votos') or 2)
    umbral_titulo = int(extra.get('umbral_titulo') or UMBRAL_TITULO_DEFECTO)
    umbral_cuerpo = int(extra.get('umbral_cuerpo') or UMBRAL_CUERPO_DEFECTO)
    progreso = progress_callback or (lambda pct, msg: None)

    # --- contexto de marca (funcion existente, se conserva para la columna de auditoria) ---
    progreso(71, 'Extrayendo contexto de la marca y sus variantes…')
    for row in rows:
        if row.get('is_duplicate'):
            row['Contexto analizado'] = '-'
        else:
            row['Contexto analizado'] = _contexto_marca(
                _texto_fila(row, km), _titulo_fila(row, km), brand, aliases)

    # --- agrupacion ---
    progreso(73, 'Agrupando notas equivalentes…')
    grupos, mapa = construir_grupos(rows, km, umbral_titulo, umbral_cuerpo)
    progreso(75, '%d grupos (notas equivalentes comparten etiqueta)' % len(grupos))

    # --- etiquetado ---
    etiquetas = etiquetar_grupos(cfg, grupos, progreso, tam_lote=tam_lote, workers=workers,
                                 votos=votos)
    cambios = canonizar_subtemas(etiquetas)
    if cambios and progress_callback:
        progreso(93, 'Sub-temas unificados: %d' % cambios)

    # --- lista de Temas: fija del cliente o generada desde el propio archivo ---
    if tax is None:
        tax = proponer_taxonomia(cfg, grupos, etiquetas,
                                 objetivo=int(extra.get('cubos_objetivo') or 16),
                                 progress=progress_callback and progreso)
        _ULTIMO_RESUMEN['taxonomia'] = list(tax.get('temas') or [])
        _ULTIMO_RESUMEN['modo_taxonomia'] = 'automatica'
    else:
        _ULTIMO_RESUMEN['taxonomia'] = list(tax.get('temas') or [])
        _ULTIMO_RESUMEN['modo_taxonomia'] = 'fija'
    _ULTIMO_RESUMEN['taxonomia_detalle'] = {'temas': list(tax.get('temas') or []),
                                            'reglas': list(tax.get('reglas') or []),
                                            'nota': tax.get('nota', '')}

    corregidos = aplicar_guarda_tono(grupos, etiquetas, brand, aliases)
    if corregidos:
        _ULTIMO_RESUMEN['tono_corregido_por_guarda'] = corregidos
        if progress_callback:
            progreso(93, 'Guarda del tono: %d Negativos sin señalamiento pasaron a Neutro' % len(corregidos))

    # --- tema por reglas + lista cerrada ---
    temas, origen = asignar_temas(cfg, grupos, etiquetas, tax, progreso)

    # --- PKL del cliente: sobreescribe tono y/o tema sin perder el subtema ---
    plan_tone = tone_model is not None
    plan_theme = theme_model is not None
    pkl_cache: Dict[int, Tuple[Optional[str], Optional[str]]] = {}
    if plan_tone or plan_theme:
        from pkl_classifier import _safe_predict, format_theme_label, map_tone_label
        for g in grupos:
            e = etiquetas[g['grupo']]
            ctx = str(rows[g['idxs'][0]].get('Contexto analizado', '') or '')
            p_tone = map_tone_label(_safe_predict(tone_model, [ctx], 'tono')[0]) if plan_tone else None
            p_theme = format_theme_label(_safe_predict(theme_model, [ctx], 'tema')[0]) if plan_theme else None
            pkl_cache[g['grupo']] = (p_tone, p_theme)
            if p_tone:
                e['tono'] = p_tone
            if p_theme:
                temas[g['grupo']] = p_theme
                origen[g['grupo']] = 'pkl'
                from ai_analyzer import ensure_subtema_distinct_from_tema
                e['sub_tema'] = ensure_subtema_distinct_from_tema(
                    p_theme, e['sub_tema'], brand, g['titulo'], ctx)

    # --- volcado a las filas ---
    for i, row in enumerate(rows):
        if row.get('is_duplicate'):
            row['Tono_IA'] = 'Duplicada'
            row['Tema_IA'] = '-'
            row['Subtema_IA'] = '-'
            continue
        gid = mapa.get(i)
        e = etiquetas.get(gid, {}) if gid else {}
        row['Tono_IA'] = e.get('tono') or 'Neutro'
        row['Tema_IA'] = temas.get(gid) or _cubo_mas_cercano(e.get('sub_tema', ''), _titulo_fila(row, km), tax)
        row['Subtema_IA'] = e.get('sub_tema') or 'Hecho informativo'

    _ULTIMO_RESUMEN['votos_tono'] = votos
    _ULTIMO_RESUMEN['filas'] = len(rows)
    _ULTIMO_RESUMEN['duplicadas'] = sum(1 for r in rows if r.get('is_duplicate'))
    if progress_callback:
        progreso(93, 'Etiquetado listo: %d grupos, %d cubos de tema' % (len(grupos), len(set(temas.values()))))
    return rows

# ============================================================================
# 9. Guarda determinista del tono: "el tema negativo no es tono negativo"
# ============================================================================
# El modelo pequeno tiende a marcar Negativo todo hecho tragico (un robo, El Nino, una protesta,
# una cifra de suicidios). Esta guarda aplica en codigo la regla del criterio: Negativo SOLO si hay
# un señalamiento dirigido a la marca, a su vocero o a una empresa del sector.
CRITICA_PAT = re.compile(
    r'(denunci|cuestion|sancion|critic|rechaz|exig|acusa|se[nñ]al|demand|investiga|irregular|'
    r'sobrecosto|corrup|incumpl|multa|reclam|responsabiliz|se le atribuye)', re.I)
VICTIMA_PAT = re.compile(
    r'(\brobo\b|roban|rob[oa]ron|hurto|atrac|asalt|accidente|\bmuert|fallec|herid|inundaci|'
    r'deslizamiento|incendio|sequ[ií]a|apag[oó]n|el ni[nñ]o|desempleo|suicid|\bprecio|alza|'
    r'aumento|protesta|delincuencia|homicid|violencia|aguas residuales en)', re.I)
BLANCO_EMPRESA = re.compile(r'(una empresa|una compa[nñ][ií]a|una firma|una industria|un frigor[ií]fico|'
                            r'una planta|un matadero|una av[ií]cola|la empresa|la compa[nñ][ií]a)', re.I)
NOMBRE_PROPIO = re.compile(r'(?<![.!?]\s)(?<![.!?])\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}')


def _tema_negativo(texto: str) -> bool:
    return bool(VICTIMA_PAT.search(ctrl(texto)))


def _critica_dirigida(texto: str, brand: str, aliases: Sequence[str]) -> bool:
    """True si el texto contiene un señalamiento con un blanco identificable (marca o nombre propio)."""
    t = ctrl(texto)
    if not t:
        return False
    nt = nz(t)
    marcas = [m for m in [brand] + list(aliases) if m and len(str(m)) > 3]
    for m in CRITICA_PAT.finditer(t):
        cerca = nt[max(0, m.start() - 60): m.end() + 90]
        if any(nz(x) and nz(x) in cerca for x in marcas):
            return True
        # el blanco tiene que estar pegado al verbo: si no, es una mencion incidental
        # ('la denuncia oportuna de la comunidad permitio recuperar...' NO es un señalamiento).
        ventana = t[m.end(): m.end() + 35]
        if BLANCO_EMPRESA.search(ventana) or NOMBRE_PROPIO.search(ventana):
            return True
    return False


def aplicar_guarda_tono(grupos: Sequence[dict], etiquetas: Dict[int, dict],
                        brand: str, aliases: Sequence[str]) -> List[int]:
    """Degrada a Neutro los Negativos que solo describen un hecho tragico, sin señalamiento dirigido.

    Devuelve la lista de grupos corregidos (para la auditoria de la interfaz).
    """
    corregidos = []
    for g in grupos:
        e = etiquetas.get(g['grupo'])
        if not e or e.get('tono') != 'Negativo':
            continue
        texto = '%s %s' % (g['titulo'], g.get('texto', ''))
        if _tema_negativo(texto) and not _critica_dirigida(texto, brand, aliases):
            e['tono'] = 'Neutro'
            corregidos.append(g['grupo'])
    return corregidos
