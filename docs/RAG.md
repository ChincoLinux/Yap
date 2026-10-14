# RAG Local — Índice y Recuperación Contextual Offline (#118)

Yap incorpora un motor de **Recuperación Aumentada por Generación (RAG)** completamente local, diseñado para operar en entornos educativos sin conexión a internet y sobre hardware modesto.

Este documento detalla la arquitectura, las justificaciones de diseño técnico, la formulación matemática y el manual de uso de dicho subsistema.

---

## 1. Justificación Arquitectónica: Decisiones de Diseño

### A. ¿Por qué Cero Dependencias Externas (`stdlib-only`)?
En soluciones RAG comerciales o de servidor es común utilizar herramientas como LangChain, LlamaIndex, ChromaDB, FAISS, PyTorch o Sentence-Transformers. En Yap, todas estas librerías están **estrictamente prohibidas**.

Las razones técnicas son:

1. **Restricción de Memoria RAM en Hardware Escolar (2 GB a 4 GB)**:
   - Las máquinas en aulas de computación de ChincoLinux suelen tener entre 2 GB y 4 GB de RAM.
   - El sistema operativo consume ~1.2 GB - 1.5 GB.
   - El motor de inferencia local (`llama-cli` con cuantización Q4_K_M) consume entre 1.5 GB y 2.2 GB.
   - Solo importar PyTorch (`import torch`) para correr modelos de embeddings consume entre 800 MB y 1.2 GB de memoria RAM adicional. Cargar el modelo de embeddings agrega otros 300 MB a 500 MB.
   - Al sobrepasar los 4 GB disponibles, el kernel ejecuta el **OOM Killer** (*Out of Memory*), terminando abruptamente la sesión del estudiante o bloqueando el sistema.
   - El motor BM25 nativo de Yap consume **menos de 5 MB de memoria RAM**.

2. **Empaquetado Nativo Debian (`.deb`) y Cumplimiento PEP 668**:
   - Yap se distribuye como paquete de sistema en ChincoLinux.
   - En Debian moderno, la política PEP 668 bloquea el uso de `pip install` a nivel global para preservar la estabilidad del sistema.
   - Las dependencias de machine learning tradicionales (`torch`, `transformers`, `chromadb`) harían que el paquete `.deb` pase de pesar unos pocos kilobytes a más de **2.5 GB a 4 GB**.
   - Muchos laboratorios escolares carecen de conexión estable a internet, por lo que no es viable descargar dependencias en tiempo de instalación.
   - Yap depende exclusivamente de la biblioteca estándar de Python 3 (`math`, `hashlib`, `json`, `re`, `glob`, `os`).

3. **Latencia de Arranque e Inferencia en CPU**:
   - En procesadores escolares sin aceleración GPU (ej. Intel Celeron o Core i3 de 2 núcleos), importar librerías pesadas como ChromaDB o PyTorch demora entre **4 y 12 segundos**.
   - La inferencia de embeddings en CPU suma varios cientos de milisegundos por fragmento y consulta.
   - En contraste, el motor Okapi BM25 en `stdlib` inicia en **< 10 milisegundos** y efectúa la búsqueda entre cientos de fragmentos en **~1.5 milisegundos**.

4. **Auditoría, Mantenimiento y Cero Roturas (Zero-Dep)**:
   - Los frameworks de RAG externos sufren cambios continuos de API, deprecaciones y vulnerabilidades de seguridad periódicas (CVEs).
   - El código en `stdlib` es 100% determinista, auditable línea por línea, seguro bajo AppArmor y compatible con cualquier versión de Python 3.

---

### B. ¿Por qué la Ventana de Contexto está Acotada a `MAX_CTX = 2048`?

1. **Memoria de la Caché KV (*Key-Value Cache*)**:
   - Cada token en la ventana de contexto de `llama.cpp` debe almacenarse en memoria RAM como parte de la KV-Cache.
   - Mantener `MAX_CTX = 2048` permite que la KV-Cache ocupe menos de 150 MB de memoria. Si se ampliara a 8.192 o 16.384 tokens, la memoria requerida aumentaría drásticamente, colapsando equipos con 4 GB de RAM.

2. **Latencia de Evaluación de Prompt (*Time-to-First-Token*)**:
   - En CPU sin GPU, la fase de evaluación del prompt (*prompt ingestion*) es la más lenta.
   - Procesar 2048 tokens en 2 núcleos puede requerir entre 15 y 25 segundos antes de que el modelo genere la primera palabra.
   - Al limitar el aporte del RAG a un máximo de **512 tokens** (`YAP_RAG_MAX_TOKENS = 512`), la evaluación contextual toma apenas **1 a 2 segundos**, garantizando una experiencia interactiva para el estudiante.

3. **Distribución del Presupuesto de Contexto**:
   Para garantizar estabilidad y evitar cortes en la respuesta del modelo, los 2048 tokens se dividen de la siguiente manera:

| Sección | Tokens Estimados | Rol |
|---|---|---|
| **System Prompt** | ~250 tokens | Tono empático, pedagogía, restricciones de seguridad y formato. |
| **Historial (`HISTORY`)** | ~500 tokens | Contexto conversacional previo (últimos turnos). |
| **Contexto RAG** | **≤ 512 tokens** | Los 3 a 5 fragmentos más relevantes del curso o guía. |
| **Consulta del Alumno** | ~50 tokens | Pregunta actual del estudiante. |
| **Espacio de Generación (`-n 384`)**| ~384 tokens | Reserva para la redacción de la respuesta del LLM sin truncamiento. |
| **Margen de Seguridad** | ~352 tokens | Buffer para evitar desbordes ante variaciones de tokenización. |
| **Total** | **2048 tokens** | Límite máximo local (`MAX_CTX`). |

4. **Prevención del Fenómeno *Lost-in-the-Middle* en Modelos 1B/3B**:
   - Los modelos ultraligeros como Llama-3.2-1B o 3B degradan significativamente su capacidad de razonamiento cuando el contexto se satura con información redundante.
   - Proveer pocos fragmentos (top-k = 3 a 5) pero de alta precisión léxica y semántica permite que el modelo responda con exactitud sin alucinar ni ignorar las instrucciones pedagógicas.

---

## 2. Funcionamiento del Pipeline

### A. Descubrimiento de Corpus y Seguridad
El corpus es **de alumno**, y el mismo en un checkout y en un equipo instalado (#262):
- `/etc/yap/cursos/*.json`: asignaturas, resultados de aprendizaje (RAs), experiencias (EAs) y actividades (ej. `FPY1101.json`).
- `USAGE.md`: junto al código (checkout, Windows) o en `/usr/share/doc/yap/` (`.deb`, `.rpm`).
- `apps.conf` y `web.conf`: las whitelists que Yap aplica (`/etc/yap/whitelist/`), o las del repo si no hay instaladas. Cada fragmento lleva una cabecera («Aplicaciones y programas permitidos…», «Páginas y sitios web permitidos…»): sin ella, una lista de dominios no comparte ni una palabra con «¿qué páginas puedo visitar?».

La documentación de desarrollo (`docs/*.md`, `AGENTS.md`) **no** entra: antes de #262 llegaba al prompt de preguntas de alumno.

> **Seguridad contra Path Traversal**: Todas las rutas descubiertas se canonicen mediante `os.path.realpath()` y se verifica que su prefijo resida estrictamente dentro de los directorios permitidos. Enlaces simbólicos hacia rutas sensibles del sistema operativo son descartados automáticamente.

### B. Chunking Semántico
El motor no divide por caracteres arbitrarios, sino por unidades pedagógicas:
- **Cursos JSON**:
  - **Resumen general**: código, nombre, horas, semanas y descripción.
  - **Resultados de Aprendizaje (RAs)**: descripción e indicadores de logro.
  - **Experiencias de Aprendizaje (EAs)**: nombre, ponderación, horas y herramientas.
  - **Actividades**: nombre, enunciado, criterios de evaluación y variantes por dificultad (`básico`, `avanzado`).
- **Archivos Markdown**: división por encabezados (`#`, `##`, `###`) o dobles saltos de línea con un techo de 300 palabras por fragmento.

### C. Algoritmo Okapi BM25
La relevancia de cada fragmento $D$ para una consulta $Q = \{q_1, q_2, \dots, q_n\}$ se calcula según la fórmula Okapi BM25:

$$\text{Score}(D, Q) = \sum_{i=1}^n \text{IDF}(q_i) \cdot \frac{f(q_i, D) \cdot (k_1 + 1)}{f(q_i, D) + k_1 \cdot \left(1 - b + b \cdot \frac{|D|}{\text{avgdl}}\right)}$$

Donde:
- $\text{IDF}(q_i) = \ln\left( \frac{N - n(q_i) + 0.5}{n(q_i) + 0.5} + 1.0 \right)$ (usando `math.log`).
- $k_1 = 1.5$: regula la saturación de frecuencia de término.
- $b = 0.75$: ajusta la penalización por longitud del documento relativo a la media ($\text{avgdl}$).
- $N$ es el total de fragmentos en el índice y $n(q_i)$ es el número de fragmentos que contienen el token $q_i$.

### D. Caché Incremental y Persistencia Atómica
- El índice compilado se guarda en formato JSON en `~/.config/yap/index/bm25_index.json`.
- En cada ejecución, se calcula una huella SHA-256 de las tuplas `(ruta, mtime, tamaño)` de todos los archivos del corpus.
- Si el hash coincide, el índice se carga instantáneamente desde el caché.
- Si algún archivo cambia, se detecta la discrepancia y el índice se recompila en memoria y se persiste atómicamente (`.tmp` + `os.replace`), evitando escrituras corruptas o problemas de concurrencia.

### E. Inyección en `cmd_query()`
Al ingresar una consulta general:
1. Si `YAP_RAG_ENABLED=1`, se consulta el índice BM25 con la pregunta del estudiante.
2. Los fragmentos resultantes se ordenan descendentemente por puntaje y se recortan para no exceder `YAP_RAG_MAX_TOKENS = 512`.
3. Se formatean como `[Contexto recuperado por RAG local]` y se inyectan en un bloque `<|header_id|>user<|end_header_id|>` previo a la consulta en `llama-cli`.
4. Si el RAG está deshabilitado o no encuentra coincidencias, el flujo continúa de manera transparente sin degradar la experiencia ni arrojar errores.

---

## 3. Comandos CLI e Interfaz

Yap incluye comandos dedicados tanto en la CLI como en el modo interactivo REPL:

```bash
# Ver estado del RAG (activo/inactivo, ruta del índice, fragmentos, archivos)
yap rag
yap rag status

# Forzar la reconstrucción del índice y medir latencia en milisegundos
yap rag rebuild

# Realizar una búsqueda directa para depuración e inspección de puntajes BM25
yap rag buscar variables y tipos de datos
yap rag buscar criterios de evaluacion FPY1101
```

---

## 4. Variables de Entorno

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `YAP_RAG_ENABLED` | `1` | `1` para activar RAG local; `0` para desactivar por completo. |
| `YAP_RAG_TOP_K` | `5` | Número máximo de fragmentos a recuperar antes del recorte de presupuesto. |
| `YAP_RAG_MAX_TOKENS` | `512` | Presupuesto máximo de tokens permitidos para inyección en el prompt. |
| `YAP_RAG_MIN_COBERTURA` | `0.2` | Fracción mínima de las palabras de contenido de la consulta (sin stopwords) que un fragmento debe contener para entrar al prompt (#263). `0` desactiva el filtro. |

---

## 5. Pruebas y Validación

La suite de pruebas en [`tests/test_yap_rag.py`](../tests/test_yap_rag.py) valida:
- **Tokenización y normalización** en español con caracteres acentuados y puntuación.
- **Chunking semántico** de cursos JSON (extracción de RAs, EAs, variantes y criterios) y Markdown.
- **BM25 scoring**: monotonicidad de puntajes, IDF positivo y serialización/deserialización íntegra.
- **Control de presupuesto**: recorte estricto a menos de `max_tokens`.
- **Invalidación por hash**: verificación de actualización automática al modificar o agregar documentos.
- **Seguridad**: rechazo de symlinks y rutas fuera del whitelist.
- **Rendimiento bajo SLA**:
  - Tiempo de recuperación: **~1.5 ms** (SLA exige < 300 ms).
  - Tiempo de rebuild completo: **< 0.1 s** (SLA exige < 60 s).
- **Golden Set Pedagógico**: 31 consultas formuladas desde la perspectiva del estudiante evaluadas con tasa de acierto y relevancia comprobadas.

---

## 6. Medición (#214)

**Fecha:** 2026-10-13 · **Ajustes:** `RAG_TOP_K=5`, `RAG_MAX_CONTEXT_TOKENS=512`, `RAG_CHUNK_SIZE=300` · **Modelo:** ninguno — se mide la recuperación, no la generación.

```bash
python3 tests/benchmark.py --rag            # o: python3 tests/rag_eval.py
python3 tests/benchmark.py --rag --json r.json
```

El conjunto está en `tests/rag_eval/preguntas.json`: **42 preguntas de alumno** (24 del curso FPY1101, 14 de uso de Yap, 4 de whitelists), cada una con la fuente que la respalda y una marca de texto verificable, más **10 controles** cuya respuesta no está en el corpus. Una pregunta acierta si un fragmento recuperado viene de la fuente esperada y contiene la marca.

Se mide sobre **dos corpus**, porque no son el mismo:

| Corpus | Qué indexa | Ficheros | Fragmentos |
|---|---|---|---|
| desarrollo | un checkout del repo: `docs/`, `USAGE.md`, `AGENTS.md`, `whitelist/`, `cursos/` | 16 | 704 |
| instalado | un equipo con el `.deb`: sólo `/etc/yap/cursos/` | 1 | 21 |

El corpus se busca junto a `yap.py`. En el `.deb` eso es `/opt/yap/`, y `build-deb.sh` no instala allí `docs/`, `whitelist/` ni `USAGE.md`. **En el aula el RAG sólo ve los cursos.**

### Resultados

| | desarrollo | instalado |
|---|---|---|
| preguntas con respuesta en el corpus | 42/42 | **24/42** |
| recall@1 | 66.7 % | 57.1 % (100 % de lo alcanzable) |
| recall@3 | 85.7 % | 57.1 % (100 %) |
| recall@5 | 92.9 % | 57.1 % (100 %) |
| recall@8 | 92.9 % | 57.1 % (100 %) |
| la respuesta llega al prompt | 92.9 % | 57.1 % |
| tokens añadidos al prompt (media / máx) | 234 / 468 | 388 / 508 |
| latencia de `rag_retrieve` (mediana / p95) | 2.6 / 3.4 ms | 0.13 / 0.18 ms |
| construcción del índice | 9 ms | 0.5 ms |
| **controles que reciben contexto** | **10/10** | **10/10** |

### Lectura

1. **El retrieval funciona sobre lo que indexa.** En el corpus instalado acierta el 100 % de lo alcanzable en el primer fragmento.
2. **En el aula no indexa lo que el alumno pregunta sobre Yap.** Las 18 preguntas de uso y whitelists no tienen respuesta en el corpus instalado: `USAGE.md` y las whitelists existen en el equipo, pero en otras rutas.
3. **En desarrollo indexa documentación interna.** `DEPLOY.md`, `PACKAGING.md`, `SECURITY-AUDIT.md`, `ROADMAP.md` y `TRUNK-BASED.md` aparecen en el prompt de preguntas de alumno, y dos de las tres preguntas de whitelists fallan porque `DEPLOY.md` le gana a `web.conf`.
4. **Contaminación total.** Las 10 preguntas fuera del corpus reciben contexto, porque no hay score mínimo: cualquier palabra compartida («que», «es», «la») basta. En el corpus instalado eso son **~430 tokens de curso** inyectados en preguntas como «quién escribió Cien años de soledad», con un score BM25 de 0.15.

### Los tres ajustes

| Ajuste | Veredicto | Dato |
|---|---|---|
| `RAG_TOP_K=5` | **se mantiene** | recall@3 = 85.7 % → @5 = 92.9 % → @8 = 92.9 %. Bajar a 3 pierde 3 aciertos; subir a 8 no gana ninguno. |
| `RAG_MAX_CONTEXT_TOKENS=512` | **se mantiene** | Nunca recortó un acierto: «llega al prompt» = recall@5 en ambos corpus. En el corpus instalado llega a 508 tokens, así que sí limita el ruido. |
| `RAG_CHUNK_SIZE=300` | **irrelevante hoy** | Sólo parte párrafos de más de 300 palabras; la unidad real es el párrafo. Con 100, 300 o 1000 el resultado es idéntico; con 50 se pierden 2 aciertos. |

### Simulaciones (no implementadas)

Para que la siguiente decisión salga con datos, el harness simula un **score mínimo** sobre el mejor fragmento (`barrido` en el JSON):

| Corpus | Umbral | Aciertos conservados | Controles bloqueados |
|---|---|---|---|
| instalado | 2 | 24/24 | 3/10 |
| instalado | **4** | **24/24** | **7/10** |
| instalado | 6 | 20/24 | 8/10 |
| desarrollo | 4 | 39/39 | 0/10 |
| desarrollo | 6 | 38/39 | 2/10 |

Una prueba aparte con stopwords en español (sin el harness) dio, en el corpus instalado, 24/24 aciertos y 8/10 controles bloqueados con umbral 2.

Un umbral sirve en el corpus instalado y no en el de desarrollo, donde los controles puntúan tanto como los aciertos. Hay que corregir el corpus primero y volver a medir después.

### Pendiente

- **Calidad de la respuesta con y sin RAG.** Necesita `llama-cli` y el modelo; esta medición no los usa. Con lo de arriba, el valor esperado del RAG en el aula hoy se limita a las preguntas sobre el curso.
- Corpus del equipo instalado (#262) y filtro de relevancia (#263): resueltos, ver abajo.

### Tras #262 — corpus de alumno

**Fecha:** 2026-10-13. Mismo conjunto, mismos ajustes.

| | antes (instalado) | después (ambos) |
|---|---|---|
| ficheros / fragmentos | 1 / 21 | 4 / 188 |
| preguntas con respuesta en el corpus | 24/42 | **42/42** |
| recall@1 / @3 / @5 / @8 | 57.1 / 57.1 / 57.1 / 57.1 % | 66.7 / 92.9 / 92.9 / 95.2 % |
| la respuesta llega al prompt | 57.1 % | **92.9 %** |
| tokens al prompt (media / máx) | 388 / 508 | 261 / 499 |
| latencia `rag_retrieve` (mediana) | 0.13 ms | 0.63 ms |
| documentos de desarrollo en el prompt | — (checkout: sí) | **ninguno** |
| controles que reciben contexto | 10/10 | 10/10 |

Desarrollo e instalado indexan ahora exactamente lo mismo, y `tests/test_rag_eval.py` lo exige.

Fallan 3 de 42: «¿está permitido Khan Academy?» (`khanacademy.org` no comparte tokens con «khan academy»), «¿qué datos guarda la telemetría?» y «¿cómo vuelvo a ver el tutorial?» (rango 8).

**El umbral de score ya no separa.** Con este corpus, la mediana de score de los aciertos es 11.96 y el máximo de los controles 10.34. Umbral 4: 39/39 aciertos, **0/10** controles bloqueados; umbral 6: pierde 5 aciertos para bloquear 4. La simulación de la primera medición (umbral 4 → 7/10 bloqueados) dependía de un corpus de 21 fragmentos y ya no aplica. #263 tiene que buscar otra señal (stopwords, score normalizado por longitud de consulta, o proporción de términos de la consulta presentes).

### Tras #263 — filtro de relevancia

**Fecha:** 2026-10-13. Mismo conjunto y corpus de #262.

Un umbral fijo sobre el score BM25 no separaba aciertos de controles (sección anterior). La señal que sí separa es la **cobertura**: qué fracción de las palabras de contenido de la consulta —sin stopwords («que», «es», «la», «como», «hace»…)— aparece en el fragmento. `rag_retrieve` descarta los fragmentos por debajo de `RAG_MIN_COBERTURA`, y una consulta sin palabras de contenido no recupera nada.

| `RAG_MIN_COBERTURA` | la respuesta llega al prompt | controles con contexto | tokens al prompt (media) |
|---|---|---|---|
| 0 (sin filtro) | 92.9 % | 10/10 | 260 |
| **0.2 (default)** | **92.9 %** | **3/10** | 221 |
| 0.34 | 85.7 % | 1/10 | 131 |
| 0.5 | 85.7 % | 1/10 | 131 |

Se elige **0.2**: no pierde ningún acierto. 0.34 limpia casi todos los controles a costa de 3 aciertos; está disponible con `YAP_RAG_MIN_COBERTURA=0.34` si en el aula pesa más el ruido que el recall.

Los 3 controles que siguen recibiendo contexto comparten palabras reales con el corpus: «receta» (la actividad «receta para un robot» del curso), «inglés» (cambio de idioma en `USAGE.md`) y «sistema» (curso). Es el límite de un buscador léxico; ajustar más las stopwords contra 10 controles sería sobreajustar.

`tests/test_rag_eval.py` fija ahora que el filtro no pierde aciertos (lo que llega al prompt = recall@5) y un techo de 3/10 controles contaminados.

