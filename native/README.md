# Módulos Nativos de Alto Rendimiento para Yap (Rama `ultra-lowmem2`)

Este directorio contiene aceleradores nativos compilados en **Rust** y **C++**, diseñados para que Yap funcione con consumo mínimo de CPU y memoria en equipos con 2 a 3 GB de RAM (ChincoLinux / Debian 13).

---

## 1. Módulo Rust: `yap_rust_core`
**Ubicación**: `native/yap_rust_core/`

### Capacidades:
1. **Índice Invertido y Ranking BM25 Ultrarrápido (`src/bm25.rs`)**:
   - Tokenización y normalización de texto en español (remoción de acentos/tildes, minúsculas, filtrado alfanumérico).
   - Estructura de listas de posteo (`term -> HashMap<doc_id, freq>`).
   - Evaluación BM25 Okapi instantánea evaluando únicamente los fragmentos que contienen términos de la consulta.
   - Cero asignaciones dinámicas pesadas en el heap durante consultas repetitivas.
2. **Monitor Nativo de Recursos y RAM (`src/sysinfo.rs`)**:
   - En Linux: lectura directa de `/proc/meminfo` usando un búfer estático de pila de 1024 bytes en $\sim 2\ \mu\text{s}$, sin invocar subprocesos de shell.
   - En Windows: llamada Win32 directa a `GlobalMemoryStatusEx`.
   - Detección precisa de equipos de bajos recursos ($\le 3500$ MB de RAM).

### Compilación:
```bash
cd native/yap_rust_core
cargo build --release
# Genera target/release/libyap_rust_core.so (Linux) o yap_rust_core.dll (Windows)
```

---

## 2. Módulo C++: `yap_cpp_llama`
**Ubicación**: `native/yap_cpp_llama/`

### Capacidades:
1. **Enlace C-ABI Directo con libllama (`yap_llama_bridge.cpp`)**:
   - Carga del modelo GGUF en memoria compartida vía `mmap`.
   - Tamaño de lote reducido (`n_batch = 128` en lugar del estándar 512/2048), reduciendo el búfer de scratch de llama.cpp en más de un 70%.
   - Contexto optimizado (`n_ctx = 1024` o `512` según el modelo).
   - Streaming directo de tokens mediante callbacks C-ABI sin tuberías ni IPC.
2. **Descargador Automático por Inactividad (`auto-unload idle`)**:
   - Hilo reaper en segundo plano que libera el contexto y modelo de la RAM tras 5 minutos de reposo, devolviendo los recursos al sistema operativo.

### Compilación:
```bash
cd native/yap_cpp_llama
make
# O con CMake:
mkdir -p build && cd build && cmake .. && cmake --build .
```

---

## 3. Integración en Python (`yap/native_bridge.py`)

Yap detecta automáticamente si las bibliotecas nativas están compiladas en `bin/` o en las rutas del sistema:
- Si existen: activa la aceleración nativa en Rust (BM25 y detección de RAM) y C++ (inferencia en memoria).
- Si no existen: Yap recurre a su implementación pura en Python estándar (`stdlib`) y al binario `llama-cli`, garantizando compatibilidad total sin dependencias obligatorias.
