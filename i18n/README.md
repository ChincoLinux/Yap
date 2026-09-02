# i18n — traducciones de Yap

Catálogos JSON para la interfaz y los prompts del LLM.

| Archivo | Idioma | Cobertura |
|---------|--------|-----------|
| `es.json` | Español (predeterminado) | Completa |
| `en.json` | English | Completa |
| `arn.json` | Mapudungun | Parcial (comunitaria) |

Las claves ausentes en un idioma caen a español. No hace falta gettext ni compilar `.mo`.

## Uso

```
yap perfil idioma es     # español
yap perfil idioma en     # english
yap perfil idioma arn    # mapudungun
yap perfil               # ver idioma actual
```

El LLM responde en el idioma del perfil. Preferencia en `~/.config/yap/profile.json`.

## Contribuir (mapudungun)

1. Copia una clave de `es.json` a `arn.json`.
2. Traduce el valor. Conserva `{placeholders}` intactos.
3. No traduzcas nombres de comandos internos (`open_app`, códigos de curso).
4. Abre un PR. La comunidad revisa la calidad lingüística.

ISO 639-3: `arn`.
