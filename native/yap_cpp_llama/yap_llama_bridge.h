// yap_llama_bridge.h — Interfaz C-ABI de ultra-bajo consumo para inferencia en C++ con llama.cpp

#ifndef YAP_LLAMA_BRIDGE_H
#define YAP_LLAMA_BRIDGE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

typedef void (*yap_token_callback_t)(const char* token, void* user_data);
typedef bool (*yap_cancel_callback_t)(void* user_data);

typedef struct {
    uint32_t n_ctx;
    uint32_t n_threads;
    uint32_t n_batch;
    bool use_mmap;
    bool use_mlock;
    uint32_t idle_timeout_s;
} yap_llama_params_t;

typedef struct {
    uint64_t total_tokens_generated;
    uint64_t elapsed_ms;
    bool is_model_loaded;
    uint64_t ram_usage_bytes;
} yap_llama_stats_t;

// Retorna la versión del puente C++
const char* yap_cpp_bridge_version(void);

// Carga el modelo en memoria con perfil de ultra-bajo consumo (mmap, batch reducido)
int yap_llama_load_model(const char* model_path, const yap_llama_params_t* params);

// Inicia streaming de inferencia sin tuberías ni subprocesos
int yap_llama_stream_generate(
    const char* prompt,
    uint32_t max_tokens,
    float temperature,
    yap_token_callback_t on_token,
    yap_cancel_callback_t check_cancel,
    void* user_data,
    char* out_full_text,
    uint32_t max_text_len,
    yap_llama_stats_t* out_stats
);

// Libera inmediatamente el modelo de la memoria RAM
void yap_llama_unload_model(void);

// Consulta el estado de carga del modelo
bool yap_llama_is_loaded(void);

#ifdef __cplusplus
}
#endif

#endif // YAP_LLAMA_BRIDGE_H
