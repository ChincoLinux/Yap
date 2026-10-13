#!/usr/bin/env python3
"""Permite ejecutar Yap como `python3 -m yap`.

El bloque `if __name__ == "__main__"` de `yap/__init__.py` no sirve para
esto: dentro del paquete ese fichero se importa como `yap`, nunca como
`__main__`, asi que sin este fichero `-m yap` no arrancaria.
"""

import sys

from yap import main

if __name__ == "__main__":
    sys.exit(main())
