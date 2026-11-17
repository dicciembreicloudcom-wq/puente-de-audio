# Puente de Audio

Manda el sonido de tu laptop con Windows a tu iPhone por Wi-Fi, para que tus AirPods
(conectados al iPhone) escuchen los dos dispositivos a la vez, sin cambiar nada.

> Documentación detallada en español: [LEEME.md](LEEME.md)

## Cómo funciona

- Un servidor en Python captura el audio que sale de la laptop (WASAPI loopback).
- Lo transmite por la red local (Opus o PCM por WebSocket).
- El iPhone lo reproduce desde una página web en Safari, sin instalar ninguna app.
- Mientras el iPhone escucha, las bocinas de la laptop se silencian solas.
- Se anuncia como `puente-audio.local`, así la dirección es la misma en casa y con hotspot.

## Requisitos

- Windows 10/11
- Python 3 (la primera vez, `_preparar.bat` crea el entorno `.venv` e instala las dependencias de `requirements.txt`)
- iPhone y laptop en la **misma red** (Wi-Fi o hotspot del iPhone)

## Uso rápido

1. Doble clic en **`Iniciar Puente de Audio.bat`**.
2. La primera vez, permite el acceso a la red a Python en el firewall de Windows.
3. Escanea el código QR con el iPhone (o abre la dirección que aparece en Safari).
4. Toca **Escuchar**.

Para dejarlo siempre encendido en segundo plano (con un ícono junto al reloj), usa
**`Instalar en segundo plano.bat`**. Para quitarlo, **`Quitar de segundo plano.bat`**.

El puerto por defecto es `8765`; se puede cambiar con `servidor.py --puerto 9000`.

## Contenido

| Archivo | Para qué sirve |
|---|---|
| `servidor.py` | Servidor: captura el audio, lo transmite y muestra el ícono de bandeja |
| `web/` | Páginas para el iPhone (`iphone.html`) y el panel con QR (`panel.html`) |
| `Iniciar Puente de Audio.bat` | Arranca con ventana |
| `Instalar en segundo plano.bat` / `Quitar de segundo plano.bat` | Inicio automático sin ventana |
| `_preparar.bat` | Crea el entorno virtual e instala dependencias |
| `requirements.txt` | Dependencias de Python |

## Consejos para que suene fluido

- Con hotspot, desactiva **Maximizar compatibilidad** en Ajustes → Compartir Internet del iPhone.
- Lo más estable es conectar el iPhone a la laptop por cable USB con Compartir Internet.
- Si el audio se corta, sube el control de **Retraso**; si el video se ve adelantado, bájalo.
- Los AirPods agregan unos 150 ms de retraso propio que no se pueden quitar.

## Privacidad

Todo ocurre dentro de tu red local. No se envía audio a internet.
