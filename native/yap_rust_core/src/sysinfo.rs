//! sysinfo.rs — Detección nativa de memoria física y recursos en Rust con cero sobrecarga.

#[cfg(target_os = "linux")]
use std::fs::File;
#[cfg(target_os = "linux")]
use std::io::Read;

#[repr(C)]
#[derive(Debug, Copy, Clone)]
pub struct MemoryStats {
    pub total_ram_mb: u64,
    pub available_ram_mb: u64,
    pub is_low_memory: bool,
}

/// Detecta memoria total en Linux leyendo /proc/meminfo con un buffer de pila (sin allocations).
#[cfg(target_os = "linux")]
pub fn detect_ram_stats_linux() -> MemoryStats {
    let mut total_kb: u64 = 0;
    let mut avail_kb: u64 = 0;

    if let Ok(mut f) = File::open("/proc/meminfo") {
        let mut buf = [0u8; 1024];
        if let Ok(n) = f.read(&mut buf) {
            let content = match std::str::from_utf8(&buf[..n]) {
                Ok(s) => s,
                Err(_) => "",
            };

            for line in content.lines() {
                if line.starts_with("MemTotal:") {
                    total_kb = parse_meminfo_line(line);
                } else if line.starts_with("MemAvailable:") {
                    avail_kb = parse_meminfo_line(line);
                }
            }
        }
    }

    let total_mb = total_kb / 1024;
    let avail_mb = avail_kb / 1024;
    MemoryStats {
        total_ram_mb: total_mb,
        available_ram_mb: avail_mb,
        is_low_memory: total_mb > 0 && total_mb <= 3500,
    }
}

#[cfg(target_os = "linux")]
fn parse_meminfo_line(line: &str) -> u64 {
    let parts: Vec<&str> = line.split_whitespace().collect();
    if parts.len() >= 2 {
        parts[1].parse::<u64>().unwrap_or(0)
    } else {
        0
    }
}

/// Detección nativa de RAM en Windows llamando directamente a GlobalMemoryStatusEx del kernel32.
#[cfg(target_os = "windows")]
#[repr(C)]
struct MemoryStatusEx {
    dw_length: u32,
    dw_memory_load: u32,
    ull_total_phys: u64,
    ull_avail_phys: u64,
    ull_total_page_file: u64,
    ull_avail_page_file: u64,
    ull_total_virtual: u64,
    ull_avail_virtual: u64,
    ull_avail_extended_virtual: u64,
}

#[cfg(target_os = "windows")]
extern "system" {
    fn GlobalMemoryStatusEx(lp_buffer: *mut MemoryStatusEx) -> i32;
}

#[cfg(target_os = "windows")]
pub fn detect_ram_stats_windows() -> MemoryStats {
    let mut status = MemoryStatusEx {
        dw_length: std::mem::size_of::<MemoryStatusEx>() as u32,
        dw_memory_load: 0,
        ull_total_phys: 0,
        ull_avail_phys: 0,
        ull_total_page_file: 0,
        ull_avail_page_file: 0,
        ull_total_virtual: 0,
        ull_avail_virtual: 0,
        ull_avail_extended_virtual: 0,
    };

    let ok = unsafe { GlobalMemoryStatusEx(&mut status) };
    if ok != 0 {
        let total_mb = status.ull_total_phys / (1024 * 1024);
        let avail_mb = status.ull_avail_phys / (1024 * 1024);
        MemoryStats {
            total_ram_mb: total_mb,
            available_ram_mb: avail_mb,
            is_low_memory: total_mb > 0 && total_mb <= 3500,
        }
    } else {
        MemoryStats {
            total_ram_mb: 0,
            available_ram_mb: 0,
            is_low_memory: false,
        }
    }
}

/// Fallback para otros sistemas operativos Unix (BSD, macOS)
#[cfg(not(any(target_os = "linux", target_os = "windows")))]
pub fn detect_ram_stats_fallback() -> MemoryStats {
    MemoryStats {
        total_ram_mb: 0,
        available_ram_mb: 0,
        is_low_memory: false,
    }
}

pub fn get_memory_stats() -> MemoryStats {
    #[cfg(target_os = "linux")]
    return detect_ram_stats_linux();

    #[cfg(target_os = "windows")]
    return detect_ram_stats_windows();

    #[cfg(not(any(target_os = "linux", target_os = "windows")))]
    return detect_ram_stats_fallback();
}
