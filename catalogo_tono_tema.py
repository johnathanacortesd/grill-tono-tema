# -*- coding: utf-8 -*-
"""Catalogo de Tono, Tema y Sub-tema (identico al de la app menciones-tono-tema).

Se separa en su propio modulo porque este proyecto es multipropósito (limpieza + analisis):
el motor (analyzer_tono_tema.py) y la interfaz (app.py) leen de aqui. No editar a mano sin
correr el autotest: las reglas de tono y los cubos de Tema son la parte que mas afecta el
resultado.
"""

TONOS = ("Positivo", "Neutro", "Negativo")
MIN_PAL, MAX_PAL = 3, 7

# ---------------------------------------------------------------- temperatura del tono
CRITERIOS_TONO = {
 "Aspectual estricto (recomendado)": "El tono mide SOLO lo que se dice de la entidad, de su vocero o de sus funcionarios.\n- Positivo: la entidad o su vocero es sujeto de un hecho favorable (obra entregada, avance,\n  beneficio para la comunidad, programa, reconocimiento, cifra buena, declaracion que los deja bien).\n- Negativo: existe critica, reclamo, sancion, denuncia o evaluacion negativa DIRIGIDA a la entidad,\n  a su administracion o a sus funcionarios.\n- LA PREGUNTA CLAVE antes de escribir Negativo: ¿de quien habla la nota? Si la entidad o su vocero\n  NO aparece como responsable, señalado o protagonista de la critica, el tono es Neutro. Los temas\n  tristes o graves NO son Negativo para la entidad: muertes, suicidio, delincuencia, desempleo,\n  pobreza, inundaciones, obras inconclusas de terceros, quejas contra otros. Una nota puede\n  mencionar a la entidad y seguir siendo Neutro (la entidad estudia el problema, participa en un\n  foro, firma una alianza o es una voz mas entre varias).\n- EL TEMA NO DECIDE EL TONO. Si la entidad publica un informe, estudio, encuesta o campaña sobre un\n  problema (desempleo, salud mental, pobreza, violencia, inseguridad, medio ambiente), el tono es\n  Neutro, y Positivo si la entidad aparece como autora de un aporte (diagnostico, propuesta,\n  solucion, alianza). Que el tema sea grave o triste NO hace Negativo a quien lo investiga.\n  Negativo exige siempre un ataque, critica o señalamiento CONTRA la entidad o su vocero.\n- SI LA ENTIDAD ACTUA FRENTE AL PROBLEMA, ES POSITIVO: si ayuda, dona, articula apoyos o\n  propone una solucion ante un hecho grave (incendios, inundaciones, accidentes), el tono es\n  Positivo aunque el tema sea tragico: el problema no es una falta de la entidad.\n- Neutro: todo lo demas. Incluye hechos malos sin responsable institucional (inundaciones,\n  homicidios, accidentes, robos, alzas de precios), la cobertura de OTRA entidad del mismo\n  territorio, y los casos en que el vocero denuncia a un tercero.\nAnte duda entre Positivo y Neutro, o entre Negativo y Neutro, elige Neutro.",
 "Favorabilidad del sector (para gremios)": "COMO DECIDIR EL TONO (en este orden; el primero que se cumpla gana)\nP1. La nota deja bien al sector o a la entidad: congreso o evento del gremio, campaña de\n    consumo de sus productos, exportaciones o mercados nuevos, crecimiento o cifras buenas,\n    reconocimiento, modernizacion, tecnologia, innovacion, competitividad, agenda o plan a\n    futuro, o un plan oficial que beneficia al sector aunque lo anuncie un ministerio -> Positivo.\n    Si la nota trata del sector en tono positivo o informativo y NO es una critica, es Positivo.\nP2. La nota tiene una critica, denuncia, sancion o señalamiento contra el gremio, su vocero o una\n    empresa del sector, o un hecho que se le atribuye y daña su imagen (contaminacion, malas\n    practicas, incumplimiento) -> Negativo.\nP3. Neutro SOLO si la nota no trata del sector ni lo afecta: politica nacional, otro gremio, otro\n    sector, economia del pais, resultados de otra entidad. Tambien son Neutro: las notas de\n    servicio o consejos al consumidor, las alertas economicas o de seguridad general, los datos\n    de precios y la agenda de una entidad distinta.\nNO son Neutro las notas del sector sobre tecnologia, congresos o planes: esas son Positivo.\nSI LA ENTIDAD ACTUA FRENTE AL PROBLEMA, ES POSITIVO: si el gremio o la marca ayuda, dona,\narticula apoyos, firma una alianza o propone una solucion ante un hecho grave (incendios,\ninundaciones, terremoto, crisis), el tono es Positivo aunque el tema sea tragico: el\nproblema no es una falta del sector.\nAntes de escribir Negativo confirma que la nota habla del sector: si es un tema nacional\n(protestas, fallos judiciales, politica, otro gremio) y el sector no es responsable ni\nprotagonista, es Neutro.\nEL TEMA NO DECIDE EL TONO: si el gremio o la entidad publica un informe o estudio sobre un\nproblema (desempleo, salud mental, pobreza, precios, inseguridad), no es Negativo; es Neutro o\nPositivo segun su encuadre. Negativo exige critica o hecho atribuible al sector.\nLos robos, hurtos y delitos contra granjas o empresas del sector son Neutro: son la victima,\nno la falta. Ante duda, elige Neutro."
}

# ---------------------------------------------------------------- reglas del sub-tema
REGLAS_SUBTEMA = "El Sub-tema es el HECHO concreto de la nota, en 3 a 5 palabras (nunca mas de 7).\n- Frase nominal, sin verbo conjugado al inicio (bien: 'Entrega del parque'; mal: 'Entregaron el\n  parque'). Si empiezas con un sustantivo de accion esta bien: 'Anuncio de inversiones'.\n- Sin terminar en preposicion o nexo, y sin dos puntos, comas, comillas ni barras.\n- No copies el titular ni recortes una frase del texto: sintetiza el hecho.\n- Sin repetir el nombre del gremio, de la entidad ni del medio.\n- Sin etiquetas de categoria. MAL: 'Exportaciones y mercados internacionales', 'Transformacion\n  digital en el sector'. BIEN: 'Exportacion de pollo a Estados Unidos', 'Paneles de IA en el\n  congreso avicola'.\n- Incluye el actor o el lugar cuando son lo que distingue el hecho: no 'Visita internacional' sino\n  'Visita de la embajadora de Australia'.\n- Prohibido rotulos vacios: 'noticias generales', 'gestion institucional', 'varios'.\n- Si el hecho ya esta en CANDIDATOS, copia ese texto EXACTO (mismas palabras y mayusculas).\n  Nunca crees una variante nueva de un hecho que ya tiene sub-tema."

# ---------------------------------------------------------------- ejemplos few-shot
EJEMPLOS = [
 {
  "titulo": "Sucre lo hace de nuevo: 40 mil niños y niñas inician sus clases con alimentación escolar desde el primer día",
  "sub_tema": "Inicio de clases con alimentación escolar",
  "tono": "Positivo"
 },
 {
  "titulo": "Gobernación de Sucre impulsa economía familiar y seguridad alimentaria en Toluviejo con 2 mil gallinas ponedoras",
  "sub_tema": "Gallinas ponedoras para economía familiar",
  "tono": "Positivo"
 },
 {
  "titulo": "Ciudad Natural del Golfo de Morrosquillo: la estrategia de Sucre para dinamizar el turismo",
  "sub_tema": "Ciudad Natural del Golfo de Morrosquillo",
  "tono": "Positivo"
 },
 {
  "titulo": "En Sucre destruyen más de 250 mil productos de contrabando valorados en más de 670 millones de pesos",
  "sub_tema": "Destrucción de productos de contrabando",
  "tono": "Positivo"
 },
 {
  "titulo": "Sucre abre nuevas rutas de cooperación internacional tras visita de la embajadora de Australia, Anna Chrisp",
  "sub_tema": "Cooperación internacional con Australia",
  "tono": "Positivo"
 },
 {
  "titulo": "Gobernación de Sucre aprobó más de $39 mil millones para la construcción de la Variante Sampués - Segovia- Sincelejo",
  "sub_tema": "Aprobación de recursos para la Variante Sampués",
  "tono": "Positivo"
 },
 {
  "titulo": "Por demoras en el PAE, Procuraduría suspende a exsecretario de Educación de Sucre",
  "sub_tema": "Sanción a exsecretario de Educación",
  "tono": "Negativo"
 },
 {
  "titulo": "Sancionan a exsecretario de Educación de Sucre, por demora en el PAE",
  "sub_tema": "Sanción por retraso en el PAE",
  "tono": "Negativo"
 },
 {
  "titulo": "Vía al Llano, una obra que está estancada",
  "sub_tema": "Estancamiento de la vía al Llano",
  "tono": "Negativo"
 },
 {
  "titulo": "Gobernadores del Caribe y la ANI evalúan proyecto del Canal del Dique",
  "sub_tema": "Avance del proyecto Canal del Dique",
  "tono": "Neutro"
 },
 {
  "titulo": "Alcalde de Cartagena y gobernadores de Bolívar, Sucre y Atlántico revisaron la operación del Canal del Dique",
  "sub_tema": "Operación del Canal del Dique",
  "tono": "Neutro"
 },
 {
  "titulo": "Yamil Arana, el mejor gobernador de la Región Caribe, según encuesta de Datanálisis",
  "sub_tema": "Encuesta de aprobación al gobernador Arana",
  "tono": "Neutro"
 },
 {
  "titulo": "Defensoría advierte riesgo inminente por violencia y desplazamientos en El Roble",
  "sub_tema": "Alerta temprana por desplazamientos en El Roble",
  "tono": "Neutro"
 },
 {
  "titulo": "Consolidación de la región Caribe como potencia bioenergética es inaplazable: gobernador Verano",
  "sub_tema": "Región Caribe como potencia bioenergética",
  "tono": "Neutro"
 },
 {
  "titulo": "Telecaribe/ El Reportero del Campo",
  "sub_tema": "Programa El Reportero del Campo",
  "tono": "Neutro"
 }
]
EJEMPLOS_TEMA = [
 {
  "titulo": "El gremio articula apoyo al sector productivo por los incendios forestales que afectaron 31.000 hectareas",
  "sub_tema": "Apoyo por incendios forestales",
  "tono": "Positivo"
 },
 {
  "titulo": "Un fallo del Consejo de Estado le pone limites al derecho a la protesta",
  "sub_tema": "Limites a la protesta",
  "tono": "Neutro"
 },
 {
  "titulo": "La entidad entrega ayudas a las familias afectadas por el invierno",
  "sub_tema": "Ayudas a familias afectadas",
  "tono": "Positivo"
 },
 {
  "titulo": "La entidad presentó el informe Panorama de la Juventud 2026: desempleo juvenil y salud mental en alerta",
  "sub_tema": "Informe sobre juventud y desempleo",
  "tono": "Neutro"
 },
 {
  "titulo": "El gremio advierte que la informalidad laboral sigue creciendo en el país",
  "sub_tema": "Informe sobre informalidad laboral",
  "tono": "Neutro"
 },
 {
  "titulo": "El estudio de la entidad revela brechas de salud mental en los jóvenes",
  "sub_tema": "Estudio sobre salud mental juvenil",
  "tono": "Neutro"
 },
 {
  "titulo": "Más de la mitad de los intentos de suicidio en Colombia corresponden a jóvenes entre 15 y 29 años",
  "sub_tema": "Intentos de suicidio en jóvenes",
  "tono": "Neutro"
 },
 {
  "titulo": "Obras de manejo ambiental no dan espera en la ciénaga del Totumo",
  "sub_tema": "Obras pendientes en la ciénaga",
  "tono": "Neutro"
 },
 {
  "titulo": "Muere una atleta y los especialistas en cuidados intensivos reaccionan en redes",
  "sub_tema": "Reacciones por muerte de atleta",
  "tono": "Neutro"
 },
 {
  "titulo": "Vecinos denuncian que la universidad no ha terminado la obra del bloque nuevo",
  "sub_tema": "Denuncia por obra sin terminar",
  "tono": "Negativo"
 },
 {
  "titulo": "Roban 180.000 huevos en una granja del Atlántico y la Policía recupera los camiones",
  "sub_tema": "Robo a granja del Atlántico",
  "tono": "Neutro"
 },
 {
  "titulo": "La Contraloría cuestiona los sobrecostos en la obra que ejecuta la entidad",
  "sub_tema": "Cuestionamientos por sobrecostos",
  "tono": "Negativo"
 }
]
EJEMPLOS_SECTOR = [
 {
  "titulo": "FENAVI realizará su congreso de 2028 en Barranquilla",
  "sub_tema": "Congreso avícola 2028 en Barranquilla",
  "tono": "Positivo"
 },
 {
  "titulo": "Gobierno impulsa plan para convertir a Colombia en potencia exportadora de pollo y huevo",
  "sub_tema": "Plan para exportar pollo y huevo",
  "tono": "Positivo"
 },
 {
  "titulo": "Fenavitón: el gremio avícola busca ayudar a familias damnificadas por el terremoto",
  "sub_tema": "Ayudas de Fenavi por el terremoto",
  "tono": "Positivo"
 },
 {
  "titulo": "Expertos analizan el impacto de la inteligencia artificial en la industria durante el congreso",
  "sub_tema": "Paneles de IA en el congreso avícola",
  "tono": "Positivo"
 },
 {
  "titulo": "180.000 huevos y 15 hombres armados: el millonario robo a una granja avícola del Atlántico",
  "sub_tema": "Robo a granja avícola en Sabanalarga",
  "tono": "Neutro"
 },
 {
  "titulo": "El precio del pollo asado sigue subiendo y estas son las causas",
  "sub_tema": "Aumento del precio del pollo asado",
  "tono": "Neutro"
 },
 {
  "titulo": "Campesinos denuncian que una empresa vierte aguas residuales en una quebrada",
  "sub_tema": "Denuncia por vertimientos de Mac Pollo",
  "tono": "Negativo"
 },
 {
  "titulo": "Alcalde de Cartagena y gobernadores evalúan el proyecto del Canal del Dique",
  "sub_tema": "Revisión del Canal del Dique",
  "tono": "Neutro"
 }
]

# ---------------------------------------------------------------- taxonomias de Tema
TAX_GOBIERNO = {
 "nota": "Cubos para gobernaciones, alcaldias y entidades publicas territoriales. El orden es la prioridad: lo especifico antes que lo generico.",
 "temas": [
  "Educación superior y universidad",
  "Deporte y Juegos Nacionales",
  "Electoral y político",
  "Política nacional e internacional",
  "Control, justicia y contratación",
  "Reconocimientos y liderazgo",
  "Gestión del riesgo, lluvias e inundaciones",
  "Seguridad y convivencia",
  "Salud y red hospitalaria",
  "Educación y primera infancia",
  "Vías, obra pública e infraestructura",
  "Agua, saneamiento y servicios públicos",
  "Energía, gas y transición energética",
  "Ayudas sociales y atención a comunidades",
  "Agro y desarrollo económico",
  "Turismo, cultura y patrimonio",
  "Juventud, género y participación",
  "Vivienda y hábitat",
  "Cooperación, paz y derechos humanos",
  "Gestión institucional y comunitaria",
  "Otros"
 ],
 "reglas": [
  {
   "tema": "Control, justicia y contratación",
   "claves": [
    "contraloria*",
    "procuraduria*",
    "fiscalia*",
    "disciplinari*",
    "sancion*",
    "irregular*",
    "hallazgo*",
    "corrupcion",
    "investigacion*",
    "captura",
    "carcel",
    "judicial",
    "accion popular",
    "veeduria",
    "responsabilidad fiscal",
    "contrat*",
    "licitacion*",
    "interventoria",
    "demanda",
    "proceso fiscal",
    "juzgado",
    "fiscal",
    "clientelismo",
    "fotomulta*"
   ]
  },
  {
   "tema": "Educación superior y universidad",
   "claves": [
    "universidad*",
    "unisucre",
    "consejo superior",
    "docente*",
    "rector*",
    "nomina*",
    "pregrado",
    "alma mater",
    "carrera profesional",
    "estudiantes universitarios",
    "profesor*",
    "docencia"
   ]
  },
  {
   "tema": "Deporte y Juegos Nacionales",
   "claves": [
    "juegos nacionales",
    "juegos deportivos",
    "villa olimpic*",
    "deportiv*",
    "liga*",
    "federacion deportiva",
    "softbol",
    "futbol",
    "balon",
    "deporte",
    "torneo*",
    "cancha*",
    "partido de",
    "escuadron femenino",
    "atleta*",
    "ciclismo",
    "patinaje",
    "olimpic*"
   ]
  },
  {
   "tema": "Política nacional e internacional",
   "claves": [
    "venezuela",
    "maduro",
    "cancilleria",
    "la guajira",
    "frontera",
    "cepeda",
    "barreras",
    "vicepresidencial*",
    "petro",
    "gobierno nacional",
    "vargas lleras",
    "presidencial*",
    "candidato presidencial",
    "cumbre de gobernadores",
    "tribunal de garantias",
    "uribe",
    "gustavo petro",
    "nacional e internacional"
   ]
  },
  {
   "tema": "Electoral y político",
   "claves": [
    "eleccion*",
    "electoral",
    "candidat*",
    "junta de accion",
    "jac",
    "registraduria",
    "voto",
    "votacion",
    "congreso",
    "senado",
    "senador*",
    "campana",
    "coalicion*",
    "partido",
    "aspirante*",
    "encuesta*",
    "parlamentaria",
    "bancada",
    "favorabilidad",
    "estragatega",
    "campanas politicas",
    "paloma valencia",
    "aranas",
    "aran a",
    "arana"
   ]
  },
  {
   "tema": "Reconocimientos y liderazgo",
   "claves": [
    "reconocimiento*",
    "forbes",
    "mujeres poderosas",
    "premio*",
    "galardon*",
    "homenaje*",
    "distincion*",
    "liderazgo",
    "aprobacion del gobernador",
    "mejor gobernador",
    "ranking",
    "perfil de liderazgo",
    "destacad*",
    "exaltad*",
    "proyeccion"
   ]
  },
  {
   "tema": "Gestión del riesgo, lluvias e inundaciones",
   "claves": [
    "inundacion*",
    "crecient*",
    "alerta roja",
    "alerta amarilla",
    "frente frio",
    "lluvia*",
    "ola invernal",
    "emergencia*",
    "damnificad*",
    "desbordamiento",
    "rio cauca",
    "san jorge",
    "mojana",
    "calamidad",
    "aguacero",
    "vendaval",
    "oleaje",
    "afectacion*",
    "caregato",
    "cara de gato",
    "boquete",
    "riada",
    "temporada de lluvias",
    "afectad*",
    "desastre",
    "ungrd",
    "evacuacion*",
    "condiciones adversas",
    "invierno",
    "clima*"
   ]
  },
  {
   "tema": "Seguridad y convivencia",
   "claves": [
    "seguridad(?! alimentaria)",
    "homicidio*",
    "asesinato*",
    "sicari*",
    "abigeato",
    "contrabando",
    "microtrafico",
    "policia*",
    "escuadron*",
    "patrullaje*",
    "convivencia",
    "armado",
    "criminal*",
    "delincuencia",
    "hurto*",
    "extorsion",
    "reten",
    "fuerza publica",
    "multicrimen",
    "clan del golfo",
    "dispositivo de seguridad",
    "incautacion*",
    "incautan",
    "operativo*",
    "violencia",
    "armada",
    "infanteria",
    "militar*",
    "ejercito",
    "soldado*",
    "antidron*",
    "armas",
    "anticonrabando",
    "anticontrabando*",
    "banda*",
    "generacion delincuencial"
   ]
  },
  {
   "tema": "Salud y red hospitalaria",
   "claves": [
    "hospital*",
    "ese(?= (de|centro|hospital|caimito|san|municipal))",
    "minsalud",
    "ministerio de salud",
    "fusi*",
    "salud",
    "acoso*",
    "enfermer*",
    "clinica*",
    "eps",
    "pai",
    "vacuna*",
    "dengue",
    "cancer*",
    "leishmaniasis",
    "red hospitalaria",
    "deuda hospitalaria",
    "ambulancia*",
    "hemocentro",
    "consultorio*",
    "cirugia",
    "nutricional",
    "salud mental",
    "droga*",
    "alimentos",
    "bebidas",
    "higiene",
    "hus",
    "hospitalario"
   ]
  },
  {
   "tema": "Educación y primera infancia",
   "claves": [
    "educacion*",
    "educativ*",
    "escolar*",
    "pae",
    "colegio*",
    "institucion educativa",
    "estudiante*",
    "nino*",
    "nina*",
    "primera infancia",
    "aula*",
    "matricula*",
    "escuela*",
    "anio escolar",
    "clases",
    "becas",
    "icfes",
    "rectoria",
    "jardin infantil",
    "infancia",
    "pedagogic*",
    "oferta educativa",
    "ciencia*",
    "tecnologia",
    "entornos digitales"
   ]
  },
  {
   "tema": "Vías, obra pública e infraestructura",
   "claves": [
    "via(?! al)",
    "vial*",
    "pavimentacion*",
    "obra*",
    "puente*",
    "calle*",
    "malecón",
    "malecon*",
    "anden*",
    "dique",
    "variante",
    "terraplen*",
    "acueducto*",
    "arroyo",
    "megaproyecto",
    "canalizacion*",
    "infraestructura",
    "corredor*",
    "tramo*",
    "bacheo",
    "intervencion*",
    "terminacion*",
    "estadio",
    "parque*",
    "peaje",
    "viaducto",
    "placa huella",
    "alumbrado",
    "hidroelectrica",
    "aeropuerto",
    "terminal de transporte",
    "hospital en construccion"
   ]
  },
  {
   "tema": "Agua, saneamiento y servicios públicos",
   "claves": [
    "agua potable",
    "aguas de sucre",
    "saneamiento",
    "alcantarillado*",
    "servicios publicos",
    "afinia",
    "energia electrica",
    "residuos",
    "aseo",
    "recurso hidrico",
    "cobertura total",
    "aseguramiento"
   ]
  },
  {
   "tema": "Energía, gas y transición energética",
   "claves": [
    "gas natural",
    "gas domiciliario",
    "energia solar",
    "fotovoltaic*",
    "transicion energetica",
    "biocombustible*",
    "bioenergetic*",
    "panel solar",
    "electrificacion*",
    "potencia energetica",
    "mineria",
    "hidrocarburo*"
   ]
  },
  {
   "tema": "Vivienda y hábitat",
   "claves": [
    "vivienda*",
    "habitacional*",
    "predio*",
    "titulacion*",
    "legalizacion*",
    "mejoramiento de vivienda",
    "techo*",
    "habitantes del corregimiento",
    "urbanismo"
   ]
  },
  {
   "tema": "Agro y desarrollo económico",
   "claves": [
    "agro*",
    "agricol*",
    "campesin*",
    "ganaderia",
    "ganadero*",
    "cultivo*",
    "piscicultura",
    "gallina*",
    "emprendimiento*",
    "emprendedor*",
    "empresario*",
    "economia familiar",
    "seguridad alimentaria",
    "empleo",
    "desempleo",
    "comercio",
    "productiv*",
    "pescador*",
    "alevinos",
    "finca*",
    "cafe",
    "agropecuari*",
    "empresarial*",
    "empresas verdes",
    "gremio*",
    "abigeato no"
   ]
  },
  {
   "tema": "Turismo, cultura y patrimonio",
   "claves": [
    "turismo",
    "turístic*",
    "turistic*",
    "cultur*",
    "patrimonio",
    "festival*",
    "porro",
    "cuadros vivos",
    "regata*",
    "mural*",
    "arte",
    "musica*",
    "carnaval",
    "hotel*",
    "visitante*",
    "playa*",
    "libro",
    "escritor*",
    "biblioteca",
    "gastronomia",
    "museo",
    "feria*",
    "danza",
    "vallenato",
    "bandera",
    "golfo de morrosquillo",
    "velero*",
    "cabalgata*",
    "fiestas",
    "aniversario",
    "conmemoracion*",
    "celebracion*",
    "identidad",
    "tradicion*"
   ]
  },
  {
   "tema": "Ayudas sociales y atención a comunidades",
   "claves": [
    "ayuda*",
    "canasta*",
    "donacion*",
    "sillas de ruedas",
    "subsidio*",
    "entrega de alimentos",
    "albergue*",
    "bonos",
    "jornada de atencion",
    "atencion a la comunidad",
    "apoyo social",
    "gestora social",
    "vejez",
    "discapacidad",
    "adulto mayor",
    "hambre",
    "solidaridad",
    "familias beneficiadas",
    "jornada buen futuro",
    "economias para la vida",
    "prosperidad social",
    "poblacion vulnerable",
    "beneficiari*"
   ]
  },
  {
   "tema": "Juventud, género y participación",
   "claves": [
    "joven*",
    "juventud*",
    "genero",
    "mujer*",
    "violencia politica",
    "participacion ciudadana",
    "consejeros juveniles",
    "mesa de juventudes",
    "igualdad",
    "victimas",
    "migrante*",
    "consejo municipal de juventud",
    "protagonistas del cambio",
    "consejo departamental de juventud",
    "juntas de accion",
    "poblacion migrante"
   ]
  },
  {
   "tema": "Cooperación, paz y derechos humanos",
   "claves": [
    "cooperacion",
    "internacional*",
    "embajador*",
    "embajada",
    "australia",
    "italia",
    "union europea",
    "laboratorio de paz",
    "paz",
    "derechos humanos",
    "defensoria",
    "desplazamiento*",
    "onu",
    "acnur",
    "unesco",
    "relaciones exteriores",
    "despojo",
    "alerta temprana",
    "proteccion de la poblacion",
    "comunidad indigena",
    "cabildo indigena",
    "etnia",
    "zenu",
    "poblacion civil",
    "conflicto armado",
    "acompanamiento a la comunidad"
   ]
  },
  {
   "tema": "Gestión institucional y comunitaria",
   "claves": [
    "gobierno",
    "consejo de gobierno",
    "alcalde",
    "alcaldia",
    "asamblea",
    "diputad*",
    "rendicion de cuentas",
    "comite*",
    "foro*",
    "visita*",
    "audiencia*",
    "sesion*",
    "posesion*",
    "nombramiento*",
    "encargo*",
    "delegado*",
    "gestion",
    "institucional",
    "convenio*",
    "alianza*",
    "comunidad*",
    "escuadron",
    "junta de accion",
    "dialogo*",
    "prioridades",
    "despacho",
    "fondo mixto",
    "impuesto*",
    "tributaria*",
    "hacienda",
    "tasa de seguridad",
    "recaudo",
    "presupuesto*",
    "pasaporte*",
    "movilidad",
    "programa",
    "columna*",
    "opinion",
    "personajes del dia",
    "ronda pais",
    "tema general",
    "especial region",
    "enfoque",
    "balance de gestion",
    "acto administrativo`"
   ]
  }
 ]
}
TAX_GREMIO = {
 "nota": "Cubos para gremios, federaciones y camaras (sector productivo). El orden es la prioridad: lo especifico antes que lo generico.",
 "temas": [
  "Ayudas y solidaridad por emergencias",
  "Precios e inflación del pollo y el huevo",
  "Cadena productiva del maíz",
  "Cría y producción avícola",
  "Política sectorial y gremios",
  "Tecnología, innovación y retos hacia 2030",
  "Congreso, foros y eventos del gremio",
  "Consumo y promoción del pollo",
  "Consumo y promoción del huevo",
  "Exportaciones y mercados internacionales",
  "Competitividad y clima de inversión",
  "Empleo y aporte del sector a la economía",
  "Seguridad y delitos contra el sector",
  "Sostenibilidad y temas ambientales",
  "Economía y política nacional",
  "Otros"
 ],
 "reglas": [
  {
   "tema": "Ayudas y solidaridad por emergencias",
   "claves": [
    "terremoto",
    "sismo",
    "damnificad*",
    "fenaviton",
    "solidarid*",
    "incendios"
   ]
  },
  {
   "tema": "Precios e inflación del pollo y el huevo",
   "claves": [
    "precio*",
    "inflacion",
    "alza",
    "caro",
    "costo* de produccion",
    "salario minimo",
    "indice del pollo",
    "subida"
   ]
  },
  {
   "tema": "Cadena productiva del maíz",
   "claves": [
    "maiz",
    "alimento animal",
    "soya",
    "siembras",
    "cadena productiva"
   ]
  },
  {
   "tema": "Cría y producción avícola",
   "claves": [
    "cria de pollos",
    "economia familiar",
    "galpon*",
    "granjas",
    "produccion de pollo"
   ]
  },
  {
   "tema": "Política sectorial y gremios",
   "claves": [
    "plan para exportar pollo",
    "medidas financieras",
    "medidas para el sector",
    "linea de credito",
    "agenda",
    "beneficios tributarios",
    "tributari*",
    "minagricultura",
    "ministro de agricultura",
    "de la espriella",
    "credito*",
    "industriales",
    "sac",
    "agro",
    "gremio*",
    "amcham"
   ]
  },
  {
   "tema": "Tecnología, innovación y retos hacia 2030",
   "claves": [
    "inteligencia artificial",
    "ia(?= )",
    "automatizacion",
    "tecnolog*",
    "digital",
    "innovacion",
    "2030",
    "transformacion",
    "continuidad del negocio",
    "hoja de ruta",
    "datos y"
   ]
  },
  {
   "tema": "Congreso, foros y eventos del gremio",
   "claves": [
    "congreso",
    "foro",
    "panel",
    "conferencista*",
    "asamblea",
    "seminario",
    "respaldo"
   ]
  },
  {
   "tema": "Consumo y promoción del pollo",
   "claves": [
    "pollo week",
    "semana del pollo",
    "pollo asado",
    "pollo frito",
    "platos de pollo",
    "restaurante*",
    "gastronom*",
    "tulio",
    "festival",
    "comer pollo",
    "consumo de pollo"
   ]
  },
  {
   "tema": "Consumo y promoción del huevo",
   "claves": [
    "huevo*",
    "nevera",
    "ovoproducto*",
    "conservar los huevos"
   ]
  },
  {
   "tema": "Exportaciones y mercados internacionales",
   "claves": [
    "exportacion*",
    "exportar",
    "exportadora",
    "estados unidos",
    "japon",
    "china",
    "emiratos",
    "corea",
    "caribe",
    "mercados internacionales",
    "comercio internacional",
    "abrir mercados"
   ]
  },
  {
   "tema": "Competitividad y clima de inversión",
   "claves": [
    "competitividad",
    "inversion*",
    "reglas claras",
    "estabilidad y seguridad",
    "empresarios",
    "consejo gremial"
   ]
  },
  {
   "tema": "Empleo y aporte del sector a la economía",
   "claves": [
    "empleo*",
    "aporte*",
    "pib",
    "economia",
    "crecimiento",
    "industria avicola",
    "papel de la avicultura",
    "genera"
   ]
  },
  {
   "tema": "Seguridad y delitos contra el sector",
   "claves": [
    "robo*",
    "hurto*",
    "delincuente*",
    "armados",
    "furgones",
    "granja avicola",
    "seguridad"
   ]
  },
  {
   "tema": "Sostenibilidad y temas ambientales",
   "claves": [
    "olores",
    "gallinero*",
    "vertimiento*",
    "ambiental",
    "residuales",
    "sostenibilidad",
    "contaminacion",
    "demanda*"
   ]
  },
  {
   "tema": "Economía y política nacional",
   "claves": [
    "dolar",
    "apagon",
    "protesta*",
    "consejo de estado",
    "el nino",
    "energia",
    "transmilenio",
    "cooperacion"
   ]
  }
 ]
}

CUBO_PROHIBIDO = {'otros', 'otro', 'varios', 'varias', 'general', 'generales', 'miscelaneo',
                  'miscelanea', 'sin clasificar', 'no clasificado', 'informacion general',
                  'sin categoria', 'pendiente'}
META_CUBO = {'entidad', 'cliente', 'empresa', 'compania', 'organizacion', 'institucion', 'institucional',
             'gubernamental', 'departamental', 'regional', 'municipal', 'general', 'generales', 'varios',
             'varias', 'otros', 'otras', 'miscelaneo', 'miscelanea', 'temas', 'asuntos'}


def taxonomia_por_nombre(nombre):
    """Devuelve la taxonomia segun el nombre que muestra la interfaz."""
    n = str(nombre or '').lower()
    if 'gremio' in n or 'sector' in n:
        return TAX_GREMIO
    return TAX_GOBIERNO
