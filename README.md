# Limpieza y Análisis de Noticias (Grill + motor de Tono/Tema/Sub-tema)

Motor de limpieza, estructuración y análisis de dossiers de noticias de GlobalNews Group. Conserva
**todo** el pipeline de limpieza y el formato de exportación del proyecto Grill-API, y reemplaza el
análisis de Tono, Tema y Sub-tema por el motor de reglas + IA de `menciones-tono-tema`.

```text
  ____ ____  ___ _     _        _    ____ ___ 
 / ___|  _ \|_ _| |   | |      / \  |  _ \_ _|
| |  _| |_) || || |   | |     / _ \ | |_) | | 
| |_| |  _ < | || |___| |___ / ___ \|  __/| | 
 \____|_| \_\___|_____|_____/_/   \_\_|  |___|
```

---

## Qué se conservó y qué cambió

**Se conserva igual (funcionalidad de Grill-API):**

- Lectura del dossier (openpyxl / python-calamine), con recuperación de hipervínculos del XLSX.
- Limpieza y normalización: tipos de medio, región e internet desde Google Sheets, numéricos, fechas,
  horas, títulos, deduplicación avanzada de radio/TV e internet.
- Expansión de menciones y detección de duplicadas (`ID duplicada`, tono `Duplicada`).
- **Formato de salida exacto**: las columnas base y las cuatro columnas de análisis
  (`Contexto analizado`, `Tono_IA`, `Tema_IA`, `Subtema_IA`) insertadas después de `revalorización`.
- Clasificadores **PKL del cliente** (sklearn/joblib) que pueden sobreescribir tono y/o tema.
- Autenticación por `APP_PASSWORD`, tema claro/oscuro, panel de progreso, métricas y descarga.
- `ai_analyzer.py` se mantiene en el proyecto: aporta las funciones de contexto de marca que alimentan
  la columna `Contexto analizado`. Su antiguo motor de análisis (`enrich_rows_with_ai`) queda como
  legado, ya no se ejecuta.

**Se reemplaza (cerebro del análisis):**

| Antes (Grill) | Ahora (`analyzer_tono_tema.py`) |
|---|---|
| Una llamada al modelo por clúster, con prompt corto | Rúbrica ordenada de decisión **P1/P2/P3** y ejemplos etiquetados |
| Subtema y tema decididos en la misma respuesta libre | Sub-tema primero (síntesis del hecho) y después el tono |
| Sin validación del texto de la etiqueta | **Validador duro** (3-7 palabras, sin verbo inicial, sin preposición final, sin rótulos) + ciclo de reparación |
| Tema inventado por el modelo | **Lista cerrada de cubos** por tipo de cliente, asignada por reglas; el modelo solo elige dentro de la lista o propone un cubo nuevo específico |
| Etiquetas por fila con agrupación heurística | Agrupación determinista de notas equivalentes (título + palabras de contenido + 5-gramas) y etiqueta única por grupo |
| Tono decidido por el modelo | Tono con **verificación múltiple** (mayoría) + **guarda determinista**: sin señalamiento dirigido no hay Negativo |
| Sin control de cubos vacíos | **Nunca "Otros"**: si nada encaja, cubo nuevo específico; en último caso, el cubo más cercano |

---

## El motor de Tono, Tema y Sub-tema

**Regla central del tono: el tema no decide el tono.** Una nota triste o grave (desempleo, salud
mental, muertes, robos, precios) **no** es negativa para la marca. Negativo exige crítica, denuncia o
señalamiento **dirigido** a la marca, a su vocero o a sus funcionarios.

Dos criterios, seleccionables en la interfaz:

- **Aspectual estricto** — gobiernos, alcaldías y entidades públicas. El tono mide lo que la entidad
  hace o recibe; si la entidad publica un informe sobre un problema, el tono es Neutro (o Positivo si
  aparece como autora de un aporte).
- **Favorabilidad del sector** — gremios, cámaras y empresas de un sector. Cuenta cómo queda parado el
  sector aunque la marca no sea el actor; los hechos adversos sin responsable del sector siguen siendo
  Neutro.

**Sub-tema**: frase nominal de 3 a 5 palabras (máximo 7) que describe el hecho, sin repetir el nombre
de la marca, sin verbos conjugados al inicio y sin etiquetas de categoría. Los sub-temas ya usados
viajan como `CANDIDATOS` en cada lote, y al final una pasada determinista de canonización unifica
variantes del mismo hecho.

**Tema**: los cubos se generan **a partir del contenido del propio archivo** (los clientes son muy
distintos: universidades, sector público, privado, marcas, gremios, y no hay una lista fija que sirva
para todos). El proceso es: se agrupan los hechos, la IA propone cubos por bloques, una consolidación
elimina duplicados y solapamientos, y el resultado se usa como lista cerrada. De esa lista se derivan
reglas léxicas para un primer pase determinista y la IA solo interviene en lo que no casa por regla.
También puedes **descargar la lista generada** y volver a subirla en el próximo período del mismo
cliente para que los Temas sean idénticos entre meses (imprescindible para comparar en Power BI). Si
prefieres una lista fija, la interfaz ofrece las de gobierno territorial y gremio.

**Estabilización del tono (dos mecanismos, porque el modelo es pequeño):**

1. **Verificación múltiple**: cada grupo se etiqueta N veces (2 por defecto) y gana la mayoría; en un
   empate el tono cae a Neutro, que es la regla de prudencia.
2. **Guarda determinista del tono**: si un grupo quedó Negativo y el texto solo describe un hecho
   trágico (robo, El Niño, protesta, accidente, inundación, alza de precios…) sin un señalamiento con
   blanco identificable, pasa a Neutro. Es la regla del criterio escrita en código, no delegada al
   modelo. La interfaz informa cuántos casos corrigió la guarda.

Medición sobre el dossier de FENAVI (142 menciones, 99 grupos, `gpt-4.1-nano-2025-04-14`, criterio de
sector): la guarda bajó los Negativos de 9 a 2 por mención, y los dos que quedan son señalamientos
reales (vertimientos de una empresa del sector y denuncias por olores de gallineros).

Medición con etiquetas humanas (20 grupos de un dossier real, `gpt-4.1-nano-2025-04-14`):
95 % de coincidencia en tono y cero etiquetas inválidas, con 10 grupos por llamada.

---

## Configuración en la interfaz

1. **Dossier** (.xlsx) con las columnas `Título` y `Resumen - Aclaracion`.
2. **Marca o Cliente Principal** (obligatoria) y **alias** separados por coma o punto y coma.
3. **Vocero(s)** de la marca (opcional).
4. **Criterio del tono** y **Lista de Temas**.
5. **Modelos PKL del cliente** (opcional): el PKL de tono y/o el de tema sobreescriben el eje
   correspondiente; el sub-tema nunca se reemplaza por PKL.
6. **Ajustes finos**: grupos por llamada (10 recomendado con nano), llamadas en paralelo (4-8 para
   dossiers grandes), verificaciones del tono por grupo (2 por defecto), cubos objetivo cuando la lista
   es automática, umbrales de similitud de titulares y de resúmenes, y carga de una lista de Temas en
   JSON para reutilizarla con el mismo cliente.

---

## Instalación y ejecución local

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
mkdir -p .streamlit
cat <<EOF > .streamlit/secrets.toml
APP_PASSWORD = "tu_contrasena_local"
OPENAI_API_KEY = "sk-..."
REGIONES_CSV_URL = "https://.../regiones.csv"
INTERNET_CSV_URL = "https://.../internet.csv"
EOF
streamlit run app.py
```

Python recomendado: **3.12**. Streamlit Community Cloud trae 3.12 por defecto y no respeta
`runtime.txt` ni `.python-version`: la versión se elige en *Advanced settings*.

---

## Despliegue en Streamlit Community Cloud

1. Sube el repositorio y vincúlalo en [share.streamlit.io](https://share.streamlit.io).
2. Archivo de inicio: `app.py`.
3. **Advanced settings → Secrets**:

```toml
APP_PASSWORD = "tu_contrasena_de_produccion"
OPENAI_API_KEY = "sk-..."
REGIONES_CSV_URL = "https://.../regiones.csv"
INTERNET_CSV_URL = "https://.../internet.csv"
```

La clave de OpenAI se usa solo en el servidor: la app no la muestra ni la envía al navegador.

---

## Pruebas

```bash
set PYTHONPATH=.            # Windows (bash: export PYTHONPATH=.)
python -m unittest tests/test_analyzer_tono_tema.py tests/test_pkl_classifier.py \
                   tests/test_pkl_subtema_grouping.py tests/test_link_export_style.py
```

- `test_analyzer_tono_tema.py` (11): agrupación de notas equivalentes, validador, reparación,
  duplicadas, canonización de cubos, rechazo de cubos genéricos, criterio de sector, **guarda del tono**,
  **votación por mayoría** y **taxonomía automática**. **Sin API**: el modelo va simulado.
- `test_pkl_classifier.py` (16), `test_pkl_subtema_grouping.py` (6) y `test_link_export_style.py` (3):
  herencia de Grill-API para los clasificadores PKL y el formato del export.

---

## Estructura

```
app.py                    interfaz Streamlit (auth, formulario, progreso, métricas, descarga)
pipeline.py               limpieza, normalización, duplicados, expansión y export (formato Grill)
analyzer_tono_tema.py     motor de Tono, Tema y Sub-tema (reglas + IA + validador)
catalogo_tono_tema.py     rúbricas de tono, reglas de sub-tema, ejemplos y taxonomías de Tema
pkl_classifier.py         clasificadores sklearn del cliente (tono / tema)
ai_analyzer.py            contexto de marca y utilidades heredadas (motor anterior, legado)
tests/                    suite de pruebas
```

---

## Límites honestos

- El tono es juicio. Las reglas cubren la mayoría de los casos, pero una crítica irónica o una obra
  anunciada y nunca ejecutada pueden diferir de la lectura humana.
- Los sub-temas del modelo están redactados distinto a los de una persona aunque describan el mismo
  hecho; para comparar entre períodos, la columna estable es **Tema**.
- El modelo no es 100 % determinista aun con temperatura 0: guarda el XLSX que entregas como versión
  final del período.
- Si una llamada falla, esa etiqueta cae a un respaldo determinista y la app lo informa en el panel
  de resultados; conviene revisar esos casos antes de entregar.

---

## Licencia

MIT. **Mantenedor:** [Johnathan A. Cortés D.](https://github.com/johnathanacortesd)
