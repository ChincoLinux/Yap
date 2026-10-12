"""deploy-yap.sh: whitelists y el informe de despliegue (#236, #237).

#236 — las whitelists pasaban por /tmp y despues sudo mv. /tmp es
escribible por cualquier usuario del host: quien controlara
/tmp/apps.conf en esa ventana decidia que podia abrir el alumno.

#237 — RESULTS_FILE se borraba con trap EXIT, y el consejo de retry que
imprime el propio script lo usaba: el comando sugerido siempre fallaba.
"""

import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "deploy-yap.sh"


def _fuente():
    return SCRIPT.read_text(encoding="utf-8")


class TestWhitelistsNoPasanPorTmp:
    def test_no_hay_tmp_como_destino(self):
        """Ningun fichero de whitelist puede ir a un dir escribible por todos."""
        for linea in _fuente().splitlines():
            if linea.lstrip().startswith("#"):
                continue
            assert "/tmp/" not in linea, f"usa /tmp: {linea.strip()}"

    def test_no_se_usa_scp(self):
        """scp dejaba el fichero en destino y luego se movia con sudo."""
        for linea in _fuente().splitlines():
            texto = linea.strip()
            if texto.startswith("#"):
                continue
            assert not re.match(r"^\s*scp\s", texto), f"scp sigue en uso: {texto}"

    def test_el_temporal_es_un_new_en_el_destino(self):
        """El .new vive junto al fichero final, que solo puede escribir root."""
        fuente = _fuente()
        assert ".conf.new" in fuente, "no se usa un .new en el directorio destino"
        assert "/etc/yap/whitelist/apps.conf.new" in fuente
        assert "/etc/yap/whitelist/web.conf.new" in fuente

    def test_el_mv_es_dentro_del_mismo_directorio(self):
        """Un mv dentro del mismo dir es atomico: no hay whitelist a medias."""
        fuente = _fuente()
        for conf in ("apps.conf", "web.conf"):
            origen = f"/etc/yap/whitelist/{conf}.new"
            destino = f"/etc/yap/whitelist/{conf}"
            assert re.search(
                rf"mv\s+{re.escape(origen)}\s+{re.escape(destino)}", fuente
            ), f"falta mv atomico para {conf}"

    def test_el_contenido_entra_por_stdin(self):
        """Sin fichero temporal local: el cuerpo viaja por stdin de ssh."""
        assert '< "${WHITELIST_DIR}/apps.conf"' in _fuente()
        assert '< "${WHITELIST_DIR}/web.conf"' in _fuente()

    def test_sigue_comprobando_permisos_ssh(self):
        """El endurecimiento no debe quitar BatchMode ni ConnectTimeout."""
        fuente = _fuente()
        assert fuente.count("BatchMode=yes") >= 3
        assert fuente.count("ConnectTimeout=30") >= 3


class TestInformePersistente:
    def test_no_se_borra_en_trap(self):
        """#237: el trap EXIT borraba el informe antes de poder usarlo."""
        assert not re.search(
            r"""trap\s+['"].*rm .*RESULTS_FILE""", _fuente()
        ), "hay un trap que borra el informe"

    def test_informe_con_nombre_propio(self):
        """mktemp daba un nombre que nadie podia adivinar al copiar el comando."""
        fuente = _fuente()
        assert "RESULTS_FILE=$(mktemp)" not in fuente
        assert re.search(
            r'RESULTS_FILE="\$\{TMPDIR:-/tmp\}/yap-deploy-', fuente
        ), "el informe no tiene nombre predecible"

    def test_imprime_la_ruta_del_informe(self):
        assert "Informe guardado en:" in _fuente()

    def test_comando_de_retry_es_funcional(self, tmp_path):
        """El comando que imprime el script debe funcionar si se copia."""
        fuente = _fuente()

        # Extraer el comando tal cual se imprime, dentro del echo.
        linea = next(
            (texto for texto in fuente.splitlines() if "grep '|FAIL|'" in texto),
            None,
        )
        assert linea, "el script ya no imprime el comando de retry"
        dentro = "grep '|FAIL|'" + linea.split("grep '|FAIL|'", 1)[1]
        dentro = dentro.split("${C_RESET}", 1)[0].strip()

        # Sustituir $RESULTS_FILE por el log de prueba y ejecutar tal cual.
        log = tmp_path / "yap-deploy-20261012-153045.log"
        log.write_text(
            "a1|OK|instalado rama main\n"
            "a2|FAIL|setup.sh falló\n"
            "a3|OK|instalado rama main\n"
            "a4|FAIL|checkout de rama main falló\n",
            encoding="utf-8",
        )
        comando = dentro.replace("${RESULTS_FILE}", str(log))
        comando = comando.replace("$RESULTS_FILE", str(log))

        cwd = tmp_path
        r = subprocess.run(
            ["bash", "-c", comando], capture_output=True, text=True, cwd=cwd, timeout=30
        )
        assert r.returncode == 0, f"el comando impreso fallo: {r.stderr}"
        obtenidos = (cwd / "hosts-retry.txt").read_text().split()
        assert obtenidos == ["a2", "a4"], obtenidos

    def test_el_informe_no_se_borra_al_terminar(self):
        """Simulamos el bloque de reporte: el fichero sigue tras ejecutarse."""
        fuente = _fuente()
        bloque = fuente[fuente.index("RESULTS_FILE=") :]
        assert "rm -f" not in bloque, "el bloque de reporte borra el informe"


class TestAyuda:
    def test_no_exige_scp_que_ya_no_se_usa(self):
        for linea in _fuente().splitlines():
            if "instalados en el administrador" in linea:
                assert "scp" not in linea, f"la ayuda aun exige scp: {linea.strip()}"
                assert "rsync" in linea
                assert "ssh" in linea

    def test_sintaxis_valida(self):
        """Solo bash: el script es #!/usr/bin/env bash y usa mapfile y local.

        Comprobarlo con sh -n seria un error, porque en Debian/Ubuntu /bin/sh
        es dash y estas construcciones no existen alli.
        """
        assert _fuente().splitlines()[0] == "#!/usr/bin/env bash"
        r = subprocess.run(
            ["bash", "-n", str(SCRIPT)], capture_output=True, text=True, timeout=60
        )
        assert r.returncode == 0, f"bash -n: {r.stderr}"
