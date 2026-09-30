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
El motor RAG descubre automáticamente los siguientes recursos locales:
- `/etc/yap/cursos/*.json`: asignaturas, resultados de aprendizaje (RAs), experiencias (EAs) y actividades (ej. `FPY1101.json`).
- `docs/*.md`: documentación operativa y guías de desarrollo.
- `whitelist/*.conf`: listas de aplicaciones y dominios web autorizados.
- `USAGE.md` y `AGENTS.md`.

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
