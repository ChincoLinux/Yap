#!/usr/bin/env python3
"""Shim de compatibilidad: la implementacion vive en el paquete `yap/`.

Existe porque `setup.sh`, los `.spec` de RPM, el Flatpak, el `.iss` de
Windows y `build-deb.sh` todos ejecutan o instalan este fichero por su
ruta. Sin el shim habria que tocar los cinco a la vez.

Para `import yap` manda el paquete `yap/`, no este fichero: los paquetes
tienen prioridad sobre los modulos con el mismo nombre en el mismo
directorio. Asi los tests que hacen `import yap` y leen `yap.__file__`
para parsear la fuente siguen viendo la implementacion real.

Uso:
    python3 yap.py --help
    python3 -m yap --help     # lo mismo, via el paquete
"""

import os
import sys

# Al ejecutarse como script, sys.path[0] ya es el directorio del shim;
# solo se refuerza por si alguien lo llama por ruta absoluta desde otro cwd.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yap import main  # noqa: E402  — el import va tras el ajuste de sys.path

if __name__ == "__main__":
    sys.exit(main())
