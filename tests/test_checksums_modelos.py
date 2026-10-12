"""Checksums de los modelos GGUF (#235).

setup.sh validaba tamaño mínimo y magic bytes GGUF. Eso detecta un HTML
de error o un fichero truncado, no un binario alterado — y el modelo se
ejecuta en el equipo del alumno. Los mirrors de HuggingFace son terceros.
"""

import re
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SETUP = RAIZ / "setup.sh"
CHECKSUMS = RAIZ / "whitelist" / "modelos.sha256"

# Extrae las funciones del script para probarlas sin ejecutar el instalador.
FUNCIONES = (
    "hash_esperado",
    "repositorio_desde_url",
    "verificar_checksum",
)


def _definiciones():
    texto = SETUP.read_text(encoding="utf-8")
    trozos = []
    for nombre in FUNCIONES:
        i = texto.index(f"{nombre}()")
        fin = texto.index("\n}", i) + 2
        trozos.append(texto[i:fin])
    return "\n".join(trozos)


def _bash(cuerpo, checksums=None):
    """Ejecuta las funciones de setup.sh con el fichero que se le pase."""
    ruta = str(checksums or CHECKSUMS)
    script = (
        f'SCRIPT_DIR="{RAIZ}"\n'
        f'CHECKSUMS_MODELOS="{ruta}"\n' + _definiciones() + "\n" + cuerpo
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=120
    )


def _par(linea):
    partes = linea.split()
    return partes[0], partes[1], partes[2], int(partes[3])


class TestFicheroDeChecksums:
    def test_existe(self):
        assert CHECKSUMS.is_file(), "falta whitelist/modelos.sha256"

    def test_formato(self):
        """Campos validos en cada entrada."""
        for numero, linea in enumerate(
            CHECKSUMS.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            partes = linea.split()
            assert len(partes) == 4, f"linea {numero}: se esperaban 4 campos"
            archivo, repo, sha, size = partes
            assert archivo.endswith(".gguf"), f"linea {numero}: {archivo}"
            assert re.fullmatch(r"[0-9a-f]{64}", sha), f"linea {numero}: sha invalido"
            assert re.fullmatch(r"[1-9][0-9]*", size), f"linea {numero}: size invalido"

    def test_cubre_los_cuatro_origenes(self):
        """Cada URL que usa setup.sh debe tener su hash."""
        repositorios = set()
        for linea in CHECKSUMS.read_text(encoding="utf-8").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            repositorios.add(linea.split()[1])
        assert {"bartowski", "unsloth"} <= repositorios

    def test_las_dos_tallas_de_cada_repositorio(self):
        combos = set()
        for linea in CHECKSUMS.read_text(encoding="utf-8").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            archivo, repo = linea.split()[:2]
            combos.add((repo, "1B" if "-1B-" in archivo else "3B"))
        assert len(combos) == 4, f"combinaciones incompletas: {combos}"

    def test_hash_distintos_entre_repositorios(self):
        """bartowski y unsloth empaquetan el mismo modelo en binarios distintos."""
        por_archivo = {}
        for linea in CHECKSUMS.read_text(encoding="utf-8").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            archivo, _repo, sha, _s = _par(linea)
            por_archivo.setdefault(archivo, set()).add(sha)
        for archivo, hashes in por_archivo.items():
            assert len(hashes) == 2, f"{archivo}: los dos repos deben diferir"

    def test_documenta_el_origen(self):
        texto = CHECKSUMS.read_text(encoding="utf-8")
        assert "lfs.oid" in texto, "no documenta de donde salen los valores"
        assert "sha256sum" in texto, "no explica como regenerarlos"


class TestBusquedaDeHash:
    def test_encuentra_bartowski_1b(self):
        r = _bash("hash_esperado Llama-3.2-1B-Instruct-Q4_K_M.gguf bartowski")
        assert r.returncode == 0, r.stderr
        assert re.fullmatch(r"[0-9a-f]{64}", r.stdout.strip())

    def test_encuentra_unsloth_3b(self):
        r = _bash("hash_esperado Llama-3.2-3B-Instruct-Q4_K_M.gguf unsloth")
        assert r.returncode == 0, r.stderr
        assert re.fullmatch(r"[0-9a-f]{64}", r.stdout.strip())

    def test_repositorio_desconocido_no_devuelve_nada(self):
        """Un repo no declarado no debe aceptarse con el hash de otro."""
        r = _bash("hash_esperado Llama-3.2-1B-Instruct-Q4_K_M.gguf nosquien")
        assert r.returncode != 0, "devolvio un hash para un repositorio desconocido"
        assert r.stdout.strip() == ""

    def test_archivo_desconocido_no_devuelve_nada(self):
        r = _bash("hash_esperado trojan.gguf bartowski")
        assert r.returncode != 0

    def test_ignora_los_comentarios(self):
        """Los comentarios no deben leerse como entradas."""
        with tempfile.NamedTemporaryFile("w", suffix=".sha256", delete=False) as f:
            f.write("# comentario con 64 hex: " + "a" * 64 + "  bartowski  x\n")
            f.write("modelo.gguf  bartowski  " + "b" * 64 + "  10\n")
            ruta = Path(f.name)
        r = _bash("hash_esperado modelo.gguf bartowski", checksums=ruta)
        ruta.unlink()
        assert r.stdout.strip() == "b" * 64


class TestExtraccionDeRepositorio:
    def test_huggingface(self):
        r = _bash(
            "repositorio_desde_url "
            "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/x.gguf"
        )
        assert r.stdout.strip() == "bartowski"

    def test_mirror_tambien(self):
        """El mirror es un tercero: su hash debe ser el del repo que replica."""
        r = _bash(
            "repositorio_desde_url "
            "https://hf-mirror.com/unsloth/Llama-3.2-3B-Instruct-GGUF/resolve/main/x.gguf?download=true"
        )
        assert r.stdout.strip() == "unsloth"

    def test_no_devuelve_el_host(self):
        r = _bash(
            "repositorio_desde_url https://huggingface.co/bartowski/r/resolve/main/x"
        )
        assert "huggingface" not in r.stdout


class TestVerificacion:
    def test_archivo_bueno_se_acepta(self, tmp_path):
        modelo = tmp_path / "modelo.gguf"
        contenido = b"GGUF" + b"\0" * 100
        modelo.write_bytes(contenido)
        import hashlib

        sha = hashlib.sha256(contenido).hexdigest()
        checks = tmp_path / "c.sha256"
        checks.write_text(f"modelo.gguf  bartowski  {sha}  {len(contenido)}\n")

        r = _bash(f'verificar_checksum "{modelo}" bartowski', checksums=checks)
        assert r.returncode == 0, r.stdout + r.stderr

    def test_archivo_alterado_se_rechaza(self, tmp_path):
        """Un .gguf con magic valido y contenido manipulado no debe pasar."""
        modelo = tmp_path / "modelo.gguf"
        modelo.write_bytes(b"GGUF" + b"\0" * 100)
        import hashlib

        sha = hashlib.sha256(b"GGUF" + b"\0" * 101).hexdigest()
        checks = tmp_path / "c.sha256"
        checks.write_text(f"modelo.gguf  bartowski  {sha}  104\n")

        r = _bash(f'verificar_checksum "{modelo}" bartowski', checksums=checks)
        assert r.returncode != 0, "acepto un modelo alterado"
        assert "NO coincide" in r.stdout

    def test_el_hash_de_otro_repo_no_valide(self, tmp_path):
        """Un modelo de unsloth no debe validarse con el hash de bartowski."""
        modelo = tmp_path / "modelo.gguf"
        contenido = b"GGUF" + b"\0" * 50
        modelo.write_bytes(contenido)
        import hashlib

        sha = hashlib.sha256(contenido).hexdigest()
        checks = tmp_path / "c.sha256"
        checks.write_text(f"modelo.gguf  unsloth  {sha}  {len(contenido)}\n")

        r = _bash(f'verificar_checksum "{modelo}" bartowski', checksums=checks)
        assert r.returncode != 0, "valido con el hash de otro repositorio"

    def test_sin_checksum_publicado_avisa(self, tmp_path):
        """Avisa pero no bloquea: un modelo nuevo no debe dejar sin instalar."""
        modelo = tmp_path / "x.gguf"
        modelo.write_bytes(b"GGUF" + b"\0" * 10)
        checks = tmp_path / "c.sha256"
        checks.write_text("# nada\n")
        r = _bash(f'verificar_checksum "{modelo}" bartowski', checksums=checks)
        assert r.returncode == 2
        assert "AVISO" in r.stdout

    def test_sha256sum_ausente_avisa(self, tmp_path, monkeypatch):
        """Sin sha256sum no se puede verificar: avisa, no finge verificar."""
        import hashlib

        modelo = tmp_path / "x.gguf"
        contenido = b"GGUF" + b"\0" * 10
        modelo.write_bytes(contenido)
        checks = tmp_path / "c.sha256"
        checks.write_text(
            f"x.gguf  bartowski  {hashlib.sha256(contenido).hexdigest()}  14\n"
        )

        binario = tmp_path / "bin"
        binario.mkdir()
        # Un PATH sin sha256sum
        r = subprocess.run(
            [
                "bash",
                "-c",
                f'SCRIPT_DIR="{RAIZ}"\nCHECKSUMS_MODELOS="{checks}"\n'
                + _definiciones()
                + f'\nPATH="{binario}"\nverificar_checksum "{modelo}" bartowski',
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert r.returncode == 2
        assert "AVISO" in r.stdout


class TestIntegracion:
    def test_se_verifica_antes_de_mover(self):
        """El orden importa: si se moviera antes, ya estaría instalado."""
        texto = SETUP.read_text(encoding="utf-8")
        i_ver = texto.index('verificar_checksum "$tmp"')
        i_mv = texto.index('sudo mv "$tmp" "$dest"')
        assert i_ver < i_mv, "el mv va antes de la verificacion"

    def test_descarga_valida_tambien_el_modelo_existente(self):
        texto = SETUP.read_text(encoding="utf-8")
        assert 'verificar_checksum "$MODEL_FILE" bartowski' in texto
        assert 'verificar_checksum "$MODEL_FILE" unsloth' in texto

    def test_sintaxis(self):
        for shell in ("bash",):
            r = subprocess.run(
                [shell, "-n", str(SETUP)], capture_output=True, text=True, timeout=60
            )
            assert r.returncode == 0, r.stderr

    def test_las_urls_de_la_descarga_estan_cubiertas(self):
        """Cada repositorio que nombra el script tiene entrada publicada."""
        texto = SETUP.read_text(encoding="utf-8")
        declarados = set()
        for linea in CHECKSUMS.read_text(encoding="utf-8").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            declarados.add(linea.split()[1])
        usados = set(re.findall(r"https?://[^/]+/([^/]+)/Llama", texto))
        assert usados <= declarados, f"faltan hashes para: {usados - declarados}"


class TestValoresPublicados:
    """Los hashes concretos, fijados en el test a proposito.

    Duplicarlos aqui no es redundancia: es la segunda copia de un valor
    de seguridad. Sin esto, alterar una linea de modelos.sha256 pasa en
    verde — el fichero se valida por forma (64 hex), no por contenido.
    Verificado: se cambio 6f85a640 por 00000000 y ningun test fallo.
    """

    # SHA256 LFS de HuggingFace (GET /api/models/<repo>/tree/main, lfs.oid)
    ESPERADOS = {
        (
            "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            "bartowski",
        ): "6f85a640a97cf2bf5b8e764087b1e83da0fdb51d7c9fab7d0fece9385611df83",
        (
            "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            "bartowski",
        ): "6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff",
        (
            "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
            "unsloth",
        ): "3f5a22426976ab26cfe84dba63c1d08391717abb1af893e10f1b2968d862dcc1",
        (
            "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
            "unsloth",
        ): "6c99cc00ae910f6a532a80022cb4bc1939094527a089c29294b841c0bd87f74d",
    }

    TAMANOS = {
        "Llama-3.2-1B-Instruct-Q4_K_M.gguf": {
            "bartowski": 807694464,
            "unsloth": 807694368,
        },
        "Llama-3.2-3B-Instruct-Q4_K_M.gguf": {
            "bartowski": 2019377696,
            "unsloth": 2019377600,
        },
    }

    def _publicados(self):
        out = {}
        for linea in CHECKSUMS.read_text(encoding="utf-8").splitlines():
            if not linea.strip() or linea.lstrip().startswith("#"):
                continue
            archivo, repo, sha, size = _par(linea)
            out[(archivo, repo)] = (sha, size)
        return out

    def test_los_cuatro_estan(self):
        assert set(self.ESPERADOS) == set(
            self._publicados()
        ), "cambiaron las entradas del fichero de checksums"

    def test_los_hashes_coinciden(self):
        """Si alguien altera un hash, el test falla."""
        pub = self._publicados()
        for clave, esperado in self.ESPERADOS.items():
            assert clave in pub, f"falta {clave}"
            assert pub[clave][0] == esperado, (
                f"{clave[0]} ({clave[1]}): el hash cambio.\n"
                f"  publicado: {pub[clave][0]}\n"
                f"  esperado:  {esperado}"
            )

    def test_los_tamanos_coinciden(self):
        """El tamano publicado debe ser el real del objeto LFS."""
        pub = self._publicados()
        for archivo, por_repo in self.TAMANOS.items():
            for repo, size in por_repo.items():
                assert (
                    pub[(archivo, repo)][1] == size
                ), f"{archivo} ({repo}): tamano inesperado"

    def test_ningun_hash_es_relleno(self):
        """Un hash trivial como 0*64 pasaria la validacion de forma."""
        for (archivo, repo), (sha, _s) in self._publicados().items():
            assert len(set(sha)) > 8, f"{archivo} ({repo}): hash sospechoso {sha}"
            assert sha != "0" * 64
            assert sha != "a" * 64

    def test_ningun_hash_se_repite_entre_repositorios(self):
        """Si dos repos compartieran hash, algo esta mal copiado."""
        vistos = {}
        for (archivo, repo), (sha, _s) in self._publicados().items():
            if archivo in vistos:
                assert vistos[archivo] != sha, f"{archivo}: mismo hash en dos repos"
            vistos[archivo] = sha
