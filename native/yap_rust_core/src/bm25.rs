//! bm25.rs — Motor de indexación invertida y scoring Okapi BM25 en Rust de ultra-bajo consumo.

use std::collections::HashMap;

pub struct BM25Engine {
    pub k1: f32,
    pub b: f32,
    pub doc_lens: Vec<usize>,
    pub avg_dl: f32,
    pub postings: HashMap<String, HashMap<usize, usize>>, // term -> {doc_idx: freq}
    pub doc_freqs: HashMap<String, usize>,
    pub num_docs: usize,
}

impl BM25Engine {
    pub fn new(k1: f32, b: f32) -> Self {
        BM25Engine {
            k1,
            b,
            doc_lens: Vec::new(),
            avg_dl: 0.0,
            postings: HashMap::new(),
            doc_freqs: HashMap::new(),
            num_docs: 0,
        }
    }

    /// Normaliza texto en español: minúsculas, remoción de tildes y signos diacríticos, palabras alfanuméricas.
    pub fn tokenize(text: &str) -> Vec<String> {
        let mut tokens = Vec::new();
        let mut cur = String::with_capacity(16);

        for ch in text.chars() {
            let ch_lower = match ch {
                'Á' | 'á' => 'a',
                'É' | 'é' => 'e',
                'Í' | 'í' => 'i',
                'Ó' | 'ó' => 'o',
                'Ú' | 'ú' | 'Ü' | 'ü' => 'u',
                'Ñ' | 'ñ' => 'ñ',
                c if c.is_alphanumeric() => c.to_ascii_lowercase(),
                _ => ' ',
            };

            if ch_lower.is_alphanumeric() {
                cur.push(ch_lower);
            } else if !cur.is_empty() {
                if cur.len() >= 2 {
                    tokens.push(cur.clone());
                }
                cur.clear();
            }
        }

        if cur.len() >= 2 {
            tokens.push(cur);
        }

        tokens
    }

    /// Agrega un documento y actualiza el índice invertido.
    pub fn add_document(&mut self, doc_id: usize, text: &str) {
        let tokens = Self::tokenize(text);
        let doc_len = tokens.len();

        if doc_id >= self.doc_lens.len() {
            self.doc_lens.resize(doc_id + 1, 0);
        }
        self.doc_lens[doc_id] = doc_len;

        let mut term_counts: HashMap<String, usize> = HashMap::new();
        for t in tokens {
            *term_counts.entry(t).or_insert(0) += 1;
        }

        for (t, count) in term_counts {
            self.postings
                .entry(t)
                .or_insert_with(HashMap::new)
                .insert(doc_id, count);
        }

        self.num_docs = self.doc_lens.len();
        let total_tokens: usize = self.doc_lens.iter().sum();
        self.avg_dl = if self.num_docs > 0 {
            total_tokens as f32 / self.num_docs as f32
        } else {
            0.0
        };

        for (t, post) in &self.postings {
            self.doc_freqs.insert(t.clone(), post.len());
        }
    }

    /// Búsqueda y ponderación BM25 rápida evaluando únicamente documentos en listas de posteo relevantes.
    pub fn search(&self, query: &str, top_k: usize) -> Vec<(usize, f32)> {
        let query_tokens = Self::tokenize(query);
        if query_tokens.is_empty() || self.num_docs == 0 {
            return Vec::new();
        }

        let mut candidate_docs: HashMap<usize, ()> = HashMap::new();
        for q in &query_tokens {
            if let Some(post) = self.postings.get(q) {
                for &doc_idx in post.keys() {
                    candidate_docs.insert(doc_idx, ());
                }
            }
        }

        if candidate_docs.is_empty() {
            return Vec::new();
        }

        let mut scores: Vec<(usize, f32)> = Vec::with_capacity(candidate_docs.len());
        let n = self.num_docs as f32;

        for &doc_idx in candidate_docs.keys() {
            let doc_len = self.doc_lens[doc_idx] as f32;
            let mut score: f32 = 0.0;

            for q in &query_tokens {
                let df = match self.doc_freqs.get(q) {
                    Some(&c) => c as f32,
                    None => continue,
                };

                let tf = match self.postings.get(q).and_then(|p| p.get(&doc_idx)) {
                    Some(&f) => f as f32,
                    None => continue,
                };

                // IDF Okapi con suavizado
                let idf = ((n - df + 0.5) / (df + 0.5) + 1.0).ln();
                let denom = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_dl.max(1.0)));
                let num = tf * (self.k1 + 1.0);

                score += idf * (num / denom.max(0.0001));
            }

            if score > 0.0 {
                scores.push((doc_idx, score));
            }
        }

        // Ordenar descendente por puntuación y limitar a top_k
        scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        if scores.len() > top_k {
            scores.truncate(top_k);
        }

        scores
    }
}
