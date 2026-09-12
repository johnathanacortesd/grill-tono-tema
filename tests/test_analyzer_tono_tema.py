# ======================================
# Motor de Tono, Tema y Sub-tema (sin API: el modelo va simulado)
# ======================================
import json
import re
import unittest

import analyzer_tono_tema as A
from pipeline import KEY_MAP


def _respuestas(cfg, mensajes, **kw):
    """Modelo simulado: devuelve etiquetas malas a proposito para probar el validador."""
    prompt = ' '.join(m['content'] for m in mensajes)
    ids = [int(x) for x in re.findall(r'GRUPO id=(\d+)', prompt)]
    if 'Clasificas notas en cubos' in prompt:
        return json.dumps({'resultados': [{'id': i, 'cubo': 'Otros' if k == 0 else 'Cubos varios'}
                                          for k, i in enumerate(ids)]}, ensure_ascii=False)
    if 'Corrige SOLO estos sub-temas' in prompt:
        return json.dumps({'resultados': [{'id': i, 'sub_tema': 'Informe de gestión', 'tono': 'Neutro'}
                                          for i in ids]}, ensure_ascii=False)
    salida = []
    for k, i in enumerate(ids):
        if k == 0:
            et = ('Anuncio del congreso internacional para', 'Positivo')     # termina en preposicion
        elif k == 1:
            et = ('Entregan reconocimiento al rector', 'Positivo')           # verbo inicial
        elif k == 2:
            et = ('Noticias generales', 'Neutro')                            # rotulo vacio
        else:
            et = ('Congreso de criminología en Barranquilla', 'Neutro')
        salida.append({'id': i, 'sub_tema': et[0], 'tono': et[1]})
    return json.dumps({'resultados': salida}, ensure_ascii=False)


def _filas():
    comun = ('El rector de la Universidad presentó el informe de gestión. La universidad explicó '
             'los avances del plan de desarrollo y las metas para el próximo año en materia de '
             'matrículas, investigación y bienestar universitario.')
    return [
        {'ID Noticia': 1, 'Título': 'Universidad Simón Bolívar presenta informe de gestión',
         'Resumen - Aclaracion': comun, 'is_duplicate': False},
        {'ID Noticia': 2, 'Título': 'La Universidad Simón Bolívar presentó su informe de gestión',
         'Resumen - Aclaracion': comun + ' El documento incluye cifras de empleabilidad.', 'is_duplicate': False},
        {'ID Noticia': 3, 'Título': 'Sancionan a exdirectivo de la universidad por demora en obras',
         'Resumen - Aclaracion': 'La Contraloría sancionó al exdirector de infraestructura por los '
                                 'retrasos en la entrega del bloque nuevo y los sobrecostos.', 'is_duplicate': False},
        {'ID Noticia': 4, 'Título': 'Más de la mitad de los intentos de suicidio en Colombia son jóvenes',
         'Resumen - Aclaracion': 'Un informe nacional advierte que los intentos de suicidio se '
                                 'concentran en la población joven del país.', 'is_duplicate': False},
        {'ID Noticia': 5, 'Título': 'Universidad Simón Bolívar presenta informe de gestión',
         'Resumen - Aclaracion': comun, 'is_duplicate': True, 'ID duplicada': 1},
    ]


class TestMotorTonoTema(unittest.TestCase):

    def setUp(self):
        self._real = A.llamar_llm
        A.llamar_llm = _respuestas
        self.cfg = {'brand': 'Universidad Simón Bolívar', 'aliases': ['Unisimón', 'la universidad'],
                    'voceros': [], 'criterio': list(A.CRITERIOS_TONO)[0], 'api_key': 'x', 'model': 'stub'}

    def tearDown(self):
        A.llamar_llm = self._real

    def test_agrupa_notas_equivalentes(self):
        grupos, mapa = A.construir_grupos(_filas(), KEY_MAP)
        # 4 filas utiles (la 5 es duplicada) y las dos primeras comparten hecho
        self.assertEqual(len(grupos), 3)
        self.assertEqual(mapa[0], mapa[1])
        self.assertNotIn(4, mapa)

    def test_validador_detecta_errores(self):
        self.assertIn('termina_preposicion', A.validar('Anuncio del congreso internacional para', 'Positivo', []))
        self.assertTrue(any(p.startswith('verbo_inicial') for p in A.validar('Entregan reconocimiento al rector', 'Positivo', [])))
        self.assertIn('rotulo_generico', A.validar('Noticias generales', 'Negativo', []))
        self.assertIn('largo(8)', A.validar('Una etiqueta demasiado larga para el estandar exigido', 'Neutro', []))
        self.assertEqual([x for x in A.validar('Congreso de criminología en Barranquilla', 'Neutro',
                                              ['Congreso de criminología en Barranquilla'])
                          if not x.startswith('revisar_anclaje')], [])

    def test_reparacion_deja_etiquetas_validas(self):
        rows = _filas()
        A.enrich_rows_with_ai(rows=rows, km=KEY_MAP, brand=self.cfg['brand'],
                              aliases=self.cfg['aliases'], api_key='x', model='stub',
                              extra={'criterio': self.cfg['criterio'], 'tam_lote': 10, 'workers': 1})
        for r in rows:
            if r.get('is_duplicate'):
                continue
            pr = [p for p in A.validar(r['Subtema_IA'], r['Tono_IA'], [r['Título']])
                  if not p.startswith('revisar_anclaje')]
            self.assertEqual(pr, [], 'etiqueta invalida en %s: %s' % (r['Subtema_IA'], pr))
            self.assertIn(r['Tono_IA'], A.TONOS)

    def test_nunca_otros_en_tema(self):
        rows = _filas()
        A.enrich_rows_with_ai(rows=rows, km=KEY_MAP, brand=self.cfg['brand'],
                              aliases=self.cfg['aliases'], api_key='x', model='stub',
                              extra={'criterio': self.cfg['criterio'], 'tam_lote': 10, 'workers': 1})
        for r in rows:
            self.assertNotEqual(A.nz(r['Tema_IA']), 'otros')
            self.assertTrue(str(r['Tema_IA']).strip())

    def test_duplicadas_conservan_su_marca(self):
        rows = _filas()
        A.enrich_rows_with_ai(rows=rows, km=KEY_MAP, brand=self.cfg['brand'],
                              aliases=self.cfg['aliases'], api_key='x', model='stub',
                              extra={'criterio': self.cfg['criterio'], 'tam_lote': 10, 'workers': 1})
        dup = rows[4]
        self.assertEqual(dup['Tono_IA'], 'Duplicada')
        self.assertEqual(dup['Tema_IA'], '-')
        self.assertEqual(dup['Subtema_IA'], '-')
        self.assertEqual(dup['Contexto analizado'], '-')

    def test_canoniza_cubos_nuevos(self):
        temas = {1: 'Prevención del suicidio', 2: 'Prevención del suicidio en Barranquilla',
                 3: 'Prevención del suicidio', 4: 'Formación en criminología'}
        cambios = A.canonizar_cubos(temas, A.taxonomia_por_nombre('Gobierno territorial'))
        self.assertGreaterEqual(cambios, 1)
        self.assertEqual(len(set(temas.values())), 2)

    def test_cubo_valido_rechaza_genericos(self):
        tax = A.taxonomia_por_nombre('Gremio o sector')
        for malo in ('Otros', 'Otros temas', 'Información general', 'Actividad institucional', 'Varios'):
            self.assertIsNone(A.cubo_valido(malo, tax, True), malo)
        self.assertEqual(A.cubo_valido('Trámite de pasaportes', tax, True), 'Trámite de pasaportes')

    def test_criterio_sector_anade_ejemplos(self):
        base = A.prompt_sistema({'brand': 'X', 'aliases': [], 'voceros': [],
                                 'criterio': list(A.CRITERIOS_TONO)[0]})
        sector = A.prompt_sistema({'brand': 'X', 'aliases': [], 'voceros': [],
                                   'criterio': 'Favorabilidad del sector (para gremios)'})
        self.assertGreater(len(sector), len(base))
        self.assertIn('sector', sector)
        self.assertIn('P1.', sector)

    def test_guarda_tono_baja_los_falsos_negativos(self):
        casos = [
            ('Roban 180.000 huevos en una granja y la denuncia oportuna de la comunidad permitio '
             'recuperar los camiones', 'Neutro'),
            ('El Nino enciende las alarmas: crece el riesgo para el agua y la energia', 'Neutro'),
            ('Un fallo del Consejo de Estado le pone limites al derecho a la protesta', 'Neutro'),
            ('Campesinos denuncian que una empresa vierte aguas residuales en una quebrada', 'Negativo'),
            ('Vecinos denuncian que Mac Pollo contamina la cienaga con vertimientos', 'Negativo'),
        ]
        for texto, esperado in casos:
            grupos = [{'grupo': 1, 'titulo': texto, 'texto': texto}]
            et = {1: {'tono': 'Negativo', 'sub_tema': 'x'}}
            A.aplicar_guarda_tono(grupos, et, 'Universidad Simon Bolivar', ['la universidad'])
            self.assertEqual(et[1]['tono'], esperado, texto[:60])

    def test_voto_mayoria_empata_en_neutro(self):
        votos = [{1: {'sub_tema': 'Robo en granja', 'tono': 'Negativo'}},
                 {1: {'sub_tema': 'Robo en granja', 'tono': 'Neutro'}},
                 {1: {'sub_tema': 'Robo en la granja', 'tono': 'Positivo'}}]
        comb = A._voto_mayoria(votos, [1])
        self.assertEqual(comb[1]['tono'], 'Neutro')
        self.assertEqual(comb[1]['sub_tema'], 'Robo en granja')

    def test_taxonomia_automatica_desde_el_archivo(self):
        temas = ['Eventos y Congresos', 'Salud Mental y Prevencion', 'Seguridad y Criminologia']

        def _stub(cfg, mensajes, **kw):
            prompt = ' '.join(m['content'] for m in mensajes)
            if 'Propón entre 10 y 14' in prompt or 'CUBOS TEMATICOS' in prompt:
                return json.dumps({'cubos': temas + ['Otros', 'Varios temas']}, ensure_ascii=False)
            return json.dumps({'cubos': temas + ['Informacion general']}, ensure_ascii=False)

        real = A.llamar_llm
        A.llamar_llm = _stub
        try:
            tax = A.proponer_taxonomia({'api_key': 'x', 'model': 'stub'},
                                       [{'grupo': 1, 'titulo': 'Congreso de criminologia'}], {1: {}})
        finally:
            A.llamar_llm = real
        self.assertGreaterEqual(len(tax['temas']), 3)
        self.assertTrue(tax['reglas'], 'la taxonomia debe traer reglas para el primer pase')
        for t in tax['temas']:
            self.assertNotIn(A.nz(t), A.CUBO_PROHIBIDO)
        self.assertEqual(A.derivar_reglas(['Salud Mental y Prevencion'])[0]['tema'], 'Salud Mental y Prevencion')

    def test_guarda_mencion_baja_positivos_de_temas_ajenos(self):
        """Sin mención a la entidad no puede haber Positivo ni Negativo."""
        casos = [
            # (texto, tono que puso el modelo, tono esperado)
            ('El congresista presentó un proyecto de paz barrial para los jóvenes de la ciudad',
             'Positivo', 'Neutro'),                       # no menciona a la entidad
            ('La Universidad Simón Bolívar fue escogida como sede de la asamblea internacional',
             'Positivo', 'Positivo'),                     # sí la menciona: se respeta
            ('Vecinos denuncian que una empresa contamina la ciénaga', 'Negativo', 'Neutro'),
            ('La Asociación de Psiquiatría pidió reforzar la prevención del suicidio',
             'Negativo', 'Neutro'),
        ]
        for texto, puesto, esperado in casos:
            grupos = [{'grupo': 1, 'titulo': texto, 'texto': texto, 'autores': []}]
            et = {1: {'tono': puesto, 'sub_tema': 'Hecho de prueba'}}
            A.aplicar_guarda_mencion(grupos, et, 'Universidad Simón Bolívar', ['Unisimón'])
            self.assertEqual(et[1]['tono'], esperado, texto[:60])

    def test_regla_autor_positivo(self):
        """Si la nota la firma un vocero de la entidad, es la entidad hablando en medios."""
        grupos = [{'grupo': 1, 'titulo': 'LA IA Y LA RECONVERSIÓN LABORAL',
                   'texto': 'Columna de opinión sobre inteligencia artificial y empleo.',
                   'autores': ['José Consuegra']},
                  {'grupo': 2, 'titulo': 'Nota de otro autor', 'texto': 'Texto cualquiera.',
                   'autores': ['Redacción']}]
        et = {1: {'tono': 'Neutro', 'sub_tema': 'Reconversión laboral'}, 2: {'tono': 'Neutro', 'sub_tema': 'Otro hecho'}}
        cambiados = A.aplicar_regla_autor(grupos, et, ['José Consuegra (rector)', 'el rector'])
        self.assertEqual(et[1]['tono'], 'Positivo')
        self.assertEqual(et[2]['tono'], 'Neutro')
        self.assertEqual(cambiados, [1])

    def test_texto_fila_usa_el_cuerpo_cuando_el_resumen_viene_vacio(self):
        fila = {'CuerpoEs': 'x' * 1200, 'Resumen - Aclaracion': '', 'resumen corto': ''}
        self.assertEqual(len(A._texto_fila(fila, KEY_MAP)), 1200)
        fila2 = {'CuerpoEs': 'corto', 'Resumen - Aclaracion': 'y' * 800}
        self.assertEqual(len(A._texto_fila(fila2, KEY_MAP)), 800)

    def test_prompt_incluye_los_pasajes_de_la_entidad(self):
        grupo = {'grupo': 1, 'n': 2, 'titulo': 'Asamblea de criminología',
                 'titulos_alt': [], 'texto': 'Texto largo. La Universidad Simón Bolívar fue escogida '
                                             'como sede y su decano lo destacó. Más texto.'}
        prompt = A.prompt_lote([grupo], [], 'Universidad Simón Bolívar', ['Unisimón'])
        self.assertIn('LO QUE SE DICE DE LA ENTIDAD', prompt)
        self.assertIn('escogida', prompt)
        self.assertIn('NO decide el tono', prompt)      # el resto de la nota no decide el tono

    def test_guarda_actor_distingue_actor_de_direccion(self):
        """Ser sede escogida/organizador/colaborador es Positivo; que el evento solo ocurra ahí, no."""
        AL = ['Unisimón', 'la universidad']
        casos = [
            ('La Universidad Simón Bolívar realiza una cumbre internacional y recibe a 50 académicos',
             True),
            ('El decano de la Universidad Simón Bolívar destacó que la institución fue escogida como '
             'sede de la asamblea', True),
            ('El informe se presentó con la colaboración de dos universidades y la Universidad Simón '
             'Bolívar', True),
            ('El estudio fue elaborado por la Universidad de la Costa y el Macondo LAB de la '
             'Universidad Simón Bolívar', True),
            ('El simposio científico se realizará en el Salón Jorge Artel de la Universidad Simón '
             'Bolívar', False),
            ('El representante recordó su formación en la Universidad Simón Bolívar durante su '
             'biografía', False),
            ('El gobernador firmó una alianza para crear la Universidad de Atalaya', False),
            ('El congresista obtuvo una maestría en la Universidad de los Andes y creó una fundación',
             False),
        ]
        for texto, esperado in casos:
            obtenido = A._evidencia_actor(texto, 'Universidad Simón Bolívar', AL)
            self.assertEqual(obtenido, esperado, texto[:70])

    def test_guarda_actor_solo_en_criterio_aspectual(self):
        grupos = [{'grupo': 1, 'titulo': 'Nota sin evidencia de actor', 'texto': 'Texto.', 'autores': []}]
        et = {1: {'tono': 'Positivo', 'sub_tema': 'Hecho cualquiera'}}
        bajados, subidos = A.aplicar_guarda_actor(grupos, et, 'Universidad Simón Bolívar',
                                                 ['Unisimón'], [], 'Favorabilidad del sector (para gremios)')
        self.assertEqual(et[1]['tono'], 'Positivo')     # en sector no se toca
        self.assertEqual((bajados, subidos), ([], []))
        bajados, subidos = A.aplicar_guarda_actor(grupos, et, 'Universidad Simón Bolívar',
                                                 ['Unisimón'], [], 'Aspectual estricto (recomendado)')
        self.assertEqual(et[1]['tono'], 'Neutro')       # en aspectual sí
        self.assertEqual(bajados, [1])

    def test_orden_de_guardas_autor_gana(self):
        """La nota firmada por un vocero queda Positivo aunque no haya evidencia de actor."""
        grupos = [{'grupo': 1, 'titulo': 'LA IA Y LA RECONVERSIÓN LABORAL',
                   'texto': 'Columna de opinión.', 'autores': ['José Consuegra']}]
        et = {1: {'tono': 'Neutro', 'sub_tema': 'Reconversión laboral'}}
        A.aplicar_regla_autor(grupos, et, ['José Consuegra'])
        A.aplicar_guarda_actor(grupos, et, 'Universidad Simón Bolívar', ['Unisimón'],
                               ['José Consuegra'], 'Aspectual estricto (recomendado)')
        # el orden real del flujo es: actor primero y autor al final
        A.aplicar_regla_autor(grupos, et, ['José Consuegra'])
        self.assertEqual(et[1]['tono'], 'Positivo')

    def test_pasajes_focalizan_el_tono_en_la_entidad(self):
        """El texto se recorta a lo que se dice de la entidad (o de sus voceros)."""
        texto = ('Otra frase de relleno sin la marca. La Universidad Simón Bolívar fue escogida como '
                 'sede del congreso. Sigue texto irrelevante para el tono.')
        p = A._pasajes_entidad(texto, 'Titular', 'Universidad Simón Bolívar', ['Unisimón'])
        self.assertIn('escogida', p)
        self.assertNotIn('relleno', p)
        self.assertEqual(A._pasajes_entidad('Nota de otro tema.', 'T', 'Universidad X', []), '')
        self.assertIn('Consuegra', A._pasajes_entidad('El rector José Consuegra explicó el plan. Fin.',
                                                      'Columna', 'Universidad X', [], ['José Consuegra']))


if __name__ == '__main__':
    unittest.main()
