//! lib.rs — Punto de entrada C-ABI para yap_rust_core.

pub mod bm25;
pub mod sysinfo;

use std::ffi::{CStr, CString};
use std::os::raw::{c_char, c_float, c_int, c_ulonglong};
use std::slice;

use bm25::BM25Engine;
use sysinfo::get_memory_stats;

/// Retorna la versión del motor nativo en Rust.
#[no_mangle]
pub extern "C" fn yap_rust_version() -> *const c_char {
    static VERSION: &[u8] = b"yap_rust_core-0.2.0\0";
    VERSION.as_ptr() as *const c_char
}

/// Retorna la memoria RAM física total del sistema en MB.
#[no_mangle]
pub extern "C" fn yap_detect_total_ram_mb() -> c_ulonglong {
    get_memory_stats().total_ram_mb
}

/// Retorna la memoria RAM disponible en MB.
#[no_mangle]
pub extern "C" fn yap_detect_available_ram_mb() -> c_ulonglong {
    get_memory_stats().available_ram_mb
}

/// Retorna 1 si el equipo es de bajos recursos (RAM <= threshold_mb), 0 si no.
#[no_mangle]
pub extern "C" fn yap_is_low_memory_system(threshold_mb: c_ulonglong) -> c_int {
    let stats = get_memory_stats();
    if stats.total_ram_mb > 0 && stats.total_ram_mb <= threshold_mb {
        1
    } else {
        0
    }
}

/// Inicializa una instancia de BM25Engine en Rust.
#[no_mangle]
pub extern "C" fn yap_bm25_init(k1: c_float, b: c_float) -> *mut BM25Engine {
    let engine = Box::new(BM25Engine::new(k1, b));
    Box::into_raw(engine)
}

/// Libera la instancia de BM25Engine de la memoria.
#[no_mangle]
pub extern "C" fn yap_bm25_free(ctx: *mut BM25Engine) {
    if !ctx.is_null() {
        unsafe {
            drop(Box::from_raw(ctx));
        }
    }
}

/// Agrega un documento al índice invertido.
#[no_mangle]
pub extern "C" fn yap_bm25_add_document(
    ctx: *mut BM25Engine,
    doc_id: usize,
    text_ptr: *const c_char,
    text_len: usize,
) -> c_int {
    if ctx.is_null() || text_ptr.is_null() {
        return -1;
    }

    let text_slice = unsafe { slice::from_raw_parts(text_ptr as *const u8, text_len) };
    let text = match std::str::from_utf8(text_slice) {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let engine = unsafe { &mut *ctx };
    engine.add_document(doc_id, text);
    0
}

/// Realiza la búsqueda BM25 y llena los buffers con IDs de documentos y scores ordenados.
#[no_mangle]
pub extern "C" fn yap_bm25_search(
    ctx: *const BM25Engine,
    query_ptr: *const c_char,
    query_len: usize,
    top_k: usize,
    out_doc_ids: *mut usize,
    out_scores: *mut c_float,
    max_results: usize,
) -> c_int {
    if ctx.is_null() || query_ptr.is_null() || out_doc_ids.is_null() || out_scores.is_null() {
        return -1;
    }

    let query_slice = unsafe { slice::from_raw_parts(query_ptr as *const u8, query_len) };
    let query = match std::str::from_utf8(query_slice) {
        Ok(s) => s,
        Err(_) => return -2,
    };

    let engine = unsafe { &*ctx };
    let results = engine.search(query, top_k);

    let count = results.len().min(max_results);
    let doc_ids_slice = unsafe { slice::from_raw_parts_mut(out_doc_ids, count) };
    let scores_slice = unsafe { slice::from_raw_parts_mut(out_scores, count) };

    for i in 0..count {
        doc_ids_slice[i] = results[i].0;
        scores_slice[i] = results[i].1;
    }

    count as c_int
}
