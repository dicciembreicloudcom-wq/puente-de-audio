# Puente de Audio

Manda el sonido de tu laptop a tu iPhone por Wi-Fi, para que tus AirPods
(conectados al iPhone) escuchen los dos dispositivos sin cambiar nada.

## Dejarlo siempre encendido (recomendado)

Doble clic en **Instalar en segundo plano.bat** (solo una vez). Desde entonces el
Puente de Audio se enciende solo al prender la laptop, sin ninguna ventana: solo
aparece un **ícono azul junto al reloj** (puede estar escondido en la flechita ^).

- Clic en el ícono → muestra el código QR.
- Clic derecho → ver si tu iPhone está escuchando, activar o quitar el silencio
  de las bocinas, o **Apagar Puente de Audio**.
- Para que ya no se encienda solo: **Quitar de segundo plano.bat**.

## Cómo usarlo a mano (con ventana)

1. Doble clic en **Iniciar Puente de Audio.bat**. Se abre una ventana negra (no la cierres)
   y una página con un código QR.
2. La primera vez, Windows pregunta si permites el acceso a la red a Python:
   marca **Redes privadas y públicas** y da **Permitir acceso**.
3. Con el iPhone en el **mismo Wi-Fi**, escanea el QR con la cámara (o abre en Safari la
   dirección que aparece).
4. Toca **Escuchar**. Listo: lo que suene en la laptop se oye en tus AirPods.

Mientras el iPhone está escuchando, las bocinas de la laptop se silencian solas,
y vuelven a sonar cuando lo detienes o apagas el programa.

## Configurar una sola vez (casa y hotspot)

1. En el iPhone: Ajustes → Compartir Internet → activa **Permitir que otros se conecten**.
2. En la laptop, conéctate una vez a la red de tu iPhone y marca **Conectar automáticamente**.
   (Con el Wi-Fi de casa ya lo tienes así.)
3. En el iPhone abre la página con el QR. Arriba aparece **“Configúralo una sola vez”**:
   toca **Abrir dirección fija** (`http://puente-audio.local:8765/escuchar`) y en esa página
   haz Compartir → **Agregar a inicio**.

Desde entonces usa siempre ese ícono: funciona igual en casa (Infinitum) que con el
hotspot, y el programa detecta solo cuándo cambias de red.

## Para que se escuche fluido con el hotspot

- En el iPhone: Ajustes → Compartir Internet → **desactiva “Maximizar compatibilidad”**.
  Así el hotspot usa la banda de 5 GHz y no choca con el Bluetooth de los AirPods
  (que usa 2.4 GHz). Es el cambio que más ayuda.
- Deja activado **Retraso automático**: mide tu red y usa solo el colchón necesario.
- Lo más estable de todo: conectar el iPhone a la laptop **por cable USB** con
  Compartir Internet activado (necesitas la app “Dispositivos Apple” de la Microsoft Store).
- Los AirPods por sí solos agregan unos 150 ms de retraso; eso no se puede quitar.

## Consejos

- En Safari: Compartir → **Agregar a inicio**, para abrirlo como app.
- Si el audio se corta, sube el control de **Retraso**.
- Si el video se ve “adelantado” al sonido, baja el **Retraso**.
- Si después de usar otra app con sonido ya no se escucha, regresa a la página y toca el botón.
