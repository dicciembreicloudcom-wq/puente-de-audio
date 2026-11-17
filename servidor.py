"""
Puente de Audio: manda el sonido de esta laptop (Windows) a tu iPhone por Wi-Fi.

Captura todo lo que suena en Windows (WASAPI loopback) y lo transmite por
WebSocket a una página que abres en Safari del iPhone. Así los AirPods se
quedan conectados al iPhone y escuchas los dos dispositivos.
"""
import asyncio
import io
import json
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
from aiohttp import web, WSMsgType

PUERTO = int(sys.argv[sys.argv.index("--puerto") + 1]) if "--puerto" in sys.argv else 8765
CARPETA = Path(__file__).parent / "web"
FRAMES_POR_BLOQUE = 960  # 20 ms a 48 kHz


NOMBRE_FIJO = "puente-audio"  # el iPhone lo encuentra como http://puente-audio.local


def ip_local() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no envía nada, solo elige la interfaz de salida
        return s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    # Sin ruta a internet (p. ej. hotspot sin datos): usa cualquier dirección de red local
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith(("127.", "169.254.")):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


# ---------------------------------------------------------------- red
class Red:
    """Vigila la red: si cambias de Wi-Fi a hotspot (o al revés), actualiza la
    dirección y anuncia el nombre fijo puente-audio.local en la red nueva."""

    def __init__(self):
        self.ip = ip_local()
        self._zc = None
        self._info = None
        self._parar = threading.Event()

    @property
    def url_ip(self):
        return f"http://{self.ip}:{PUERTO}/escuchar"

    @property
    def url_fija(self):
        return f"http://{NOMBRE_FIJO}.local:{PUERTO}/escuchar"

    def iniciar(self):
        threading.Thread(target=self._bucle, daemon=True).start()

    def detener(self):
        self._parar.set()
        try:
            if self._zc:
                if self._info:
                    self._zc.unregister_service(self._info)
                self._zc.close()
        except Exception:
            pass

    def _anunciar(self):
        from zeroconf import ServiceInfo, Zeroconf
        try:
            if self._zc:
                if self._info:
                    self._zc.unregister_service(self._info)
                self._zc.close()
            self._zc, self._info = None, None
            if self.ip.startswith("127."):
                return
            self._zc = Zeroconf(interfaces=[self.ip])
            self._info = ServiceInfo(
                "_http._tcp.local.",
                f"Puente de Audio._http._tcp.local.",
                addresses=[socket.inet_aton(self.ip)],
                port=PUERTO,
                properties={"path": "/escuchar"},
                server=f"{NOMBRE_FIJO}.local.",
            )
            self._zc.register_service(self._info, allow_name_change=True)
        except Exception as e:
            print("  (no pude anunciar el nombre fijo:", e, ")")

    def _bucle(self):
        self._anunciar()
        while not self._parar.wait(3):
            nueva = ip_local()
            if nueva != self.ip:
                self.ip = nueva
                print()
                print(f"  Cambiaste de red. Nueva dirección: {self.url_ip}")
                print(f"  La dirección fija sigue igual:    {self.url_fija}")
                self._anunciar()


# ---------------------------------------------------------------- control remoto
# Solo estas teclas se pueden presionar desde el iPhone (nada más).
TECLAS = {
    "playpause": 0xB3,  # tecla multimedia Reproducir/Pausa
    "siguiente": 0xB0,  # tecla multimedia Siguiente
    "anterior": 0xB1,   # tecla multimedia Anterior
    "adelantar": 0x27,  # flecha derecha: adelanta en YouTube, Netflix, VLC...
    "atrasar": 0x25,    # flecha izquierda: regresa unos segundos
}


def presionar(accion):
    vk = TECLAS.get(accion)
    if vk is None:
        return
    import ctypes
    teclado = ctypes.windll.user32
    extendida = 0x1 if vk in (0x25, 0x27) else 0x0
    teclado.keybd_event(vk, 0, extendida, 0)
    teclado.keybd_event(vk, 0, extendida | 0x2, 0)
    print(f"  Control desde el iPhone: {accion}")


class ControlMedia:
    """Control universal: usa los controles multimedia de Windows (los mismos del
    panel de volumen), que funcionan con Spotify, YouTube, Netflix, HBO Max,
    Disney+, etc., aunque su ventana no esté al frente. Si una app no los
    soporta, se usan las teclas como respaldo."""

    SALTO = 10  # segundos que adelanta o regresa

    def __init__(self):
        self._mgr = None

    async def _sesion(self):
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        if self._mgr is None:
            self._mgr = await M.request_async()
        actual = self._mgr.get_current_session()
        sonando = lambda s: s is not None and int(s.get_playback_info().playback_status) == 4
        if sonando(actual):
            return actual
        # si lo "actual" está en pausa, preferimos la app que sí está sonando
        for s in self._mgr.get_sessions():
            if sonando(s):
                return s
        return actual

    @staticmethod
    def nombre_app(sesion) -> str:
        app = sesion.source_app_user_model_id or ""
        bajo = app.lower()
        for clave, nombre in (("spotify", "Spotify"), ("chrome", "Chrome"), ("edge", "Edge"),
                              ("firefox", "Firefox"), ("netflix", "Netflix"), ("disney", "Disney+"),
                              ("hbo", "Max"), ("max", "Max"), ("vlc", "VLC"), ("zune", "Reproductor"),
                              ("music", "Música"), ("prime", "Prime Video"), ("opera", "Opera"),
                              ("brave", "Brave")):
            if clave in bajo:
                return nombre
        return app.split("!")[-1].split("\\")[-1].removesuffix(".exe") or "la app"

    async def _mover(self, sesion, segundos) -> bool:
        import datetime
        if not sesion.get_playback_info().controls.is_playback_position_enabled:
            return False
        t = sesion.get_timeline_properties()
        pos = t.position
        # algunas apps (como Spotify) no actualizan la posición a cada rato:
        # si está sonando, le sumamos el tiempo que pasó desde su último aviso
        if int(sesion.get_playback_info().playback_status) == 4:
            try:
                pasado = datetime.datetime.now(datetime.timezone.utc) - t.last_updated_time
                if datetime.timedelta(0) < pasado < datetime.timedelta(hours=12):
                    pos += pasado
            except Exception:
                pass
        nueva = pos + datetime.timedelta(seconds=segundos)
        nueva = max(t.start_time, nueva)
        if t.end_time > t.start_time:
            nueva = min(nueva, t.end_time - datetime.timedelta(seconds=1))
        return bool(await sesion.try_change_playback_position_async(int(nueva.total_seconds() * 10_000_000)))

    async def ejecutar(self, accion) -> dict:
        if accion not in TECLAS:
            return {"ok": False}
        try:
            sesion = await self._sesion()
            if sesion is not None:
                if accion == "playpause":
                    ok = await sesion.try_toggle_play_pause_async()
                elif accion == "siguiente":
                    ok = await sesion.try_skip_next_async()
                elif accion == "anterior":
                    ok = await sesion.try_skip_previous_async()
                else:
                    ok = await self._mover(sesion, self.SALTO if accion == "adelantar" else -self.SALTO)
                if ok:
                    app = self.nombre_app(sesion)
                    print(f"  Control desde el iPhone: {accion} en {app}")
                    return {"ok": True, "app": app}
        except Exception as e:
            print("  (controles de Windows no disponibles:", e, ")")
        presionar(accion)  # respaldo: teclas
        return {"ok": True, "app": None}


# ---------------------------------------------------------------- volumen laptop
class Bocinas:
    """Silencia las bocinas de la laptop mientras alguien escucha en el iPhone."""

    def __init__(self):
        self.activo = True
        self._silenciado_por_mi = False
        self._estado_original = None

    def _endpoint(self):
        try:
            import comtypes
            comtypes.CoInitialize()
            from pycaw.pycaw import AudioUtilities
            return AudioUtilities.GetSpeakers().EndpointVolume
        except Exception as e:  # pycaw no disponible o sin bocinas
            print("  (no pude controlar el volumen:", e, ")")
            return None

    def silenciar(self):
        if not self.activo or self._silenciado_por_mi:
            return
        ep = self._endpoint()
        if ep is None:
            return
        self._estado_original = ep.GetMute()
        ep.SetMute(1, None)
        self._silenciado_por_mi = True
        print("  Bocinas de la laptop silenciadas (el sonido va al iPhone).")

    def restaurar(self):
        if not self._silenciado_por_mi:
            return
        ep = self._endpoint()
        if ep is not None:
            ep.SetMute(self._estado_original or 0, None)
        self._silenciado_por_mi = False
        print("  Bocinas de la laptop restauradas.")


# ---------------------------------------------------------------- captura
class Captura:
    """Lee el audio del dispositivo de salida predeterminado en un hilo aparte."""

    def __init__(self, al_recibir):
        self.al_recibir = al_recibir
        self.rate = 48000
        self.canales = 2
        self.nombre = "?"
        self._parar = threading.Event()
        self._hilo = threading.Thread(target=self._bucle, daemon=True)

    def iniciar(self):
        self._hilo.start()

    def detener(self):
        self._parar.set()

    def _bucle(self):
        while not self._parar.is_set():
            try:
                self._capturar()
            except Exception as e:
                print("  Error de captura, reintentando:", e)
                time.sleep(1)

    @staticmethod
    def _medidor_salida():
        """Medidor de volumen de la salida predeterminada de Windows (o None si no hay)."""
        try:
            import comtypes
            from comtypes import CLSCTX_ALL
            from pycaw.constants import CLSID_MMDeviceEnumerator
            from pycaw.pycaw import IAudioMeterInformation, IMMDeviceEnumerator
            comtypes.CoInitialize()
            enumerador = comtypes.CoCreateInstance(
                CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, comtypes.CLSCTX_INPROC_SERVER)
            disp = enumerador.GetDefaultAudioEndpoint(0, 0)
            return disp.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None).QueryInterface(
                IAudioMeterInformation)
        except Exception as e:
            print("  (no pude medir la salida de audio:", e, ")")
            return None

    def _capturar(self):
        pa = pyaudio.PyAudio()
        try:
            disp = pa.get_default_wasapi_loopback()
            self.rate = int(disp["defaultSampleRate"])
            self.canales = min(2, int(disp["maxInputChannels"])) or 2
            self.nombre = disp["name"]
            print(f"  Capturando: {self.nombre} ({self.rate} Hz, {self.canales} canales)")

            pico = [0]  # volumen más alto captado desde la última revisión

            def callback(datos, frames, info, estado):
                try:
                    m = int(np.abs(np.frombuffer(datos, dtype=np.int16)).max())
                    if m > pico[0]:
                        pico[0] = m
                except ValueError:
                    pass
                self.al_recibir(datos)
                return (None, pyaudio.paContinue)

            stream = pa.open(
                format=pyaudio.paInt16,
                channels=self.canales,
                rate=self.rate,
                input=True,
                input_device_index=disp["index"],
                frames_per_buffer=FRAMES_POR_BLOQUE,
                stream_callback=callback,
            )
            stream.start_stream()
            # Revisa cada 2 s si cambió la salida predeterminada (p. ej. conectaste otra bocina)
            medidor = self._medidor_salida()
            mudos = 0  # revisiones seguidas con sonido en la salida pero silencio en la captura
            while not self._parar.is_set() and stream.is_active():
                pico[0] = 0
                sonando = 0.0
                for _ in range(8):  # 2 s, midiendo si la salida de Windows realmente suena
                    time.sleep(0.25)
                    if medidor is not None:
                        try:
                            sonando = max(sonando, medidor.GetPeakValue())
                        except Exception:
                            medidor = None
                nuevo = pa.get_default_wasapi_loopback()["name"]
                if nuevo != self.nombre:
                    print("  Cambió la salida de audio de Windows, reconectando...")
                    break
                # Si Windows reproduce sonido pero la captura llega en silencio, la captura
                # se trabó (pasó con Zoom): se reconecta sola en vez de quedar muda.
                if sonando > 0.02 and pico[0] == 0:
                    mudos += 1
                    if mudos >= 2:
                        print("  La captura quedó muda aunque hay sonido; reconectando...")
                        break
                else:
                    mudos = 0
            stream.stop_stream()
            stream.close()
        finally:
            pa.terminate()


# ---------------------------------------------------------------- compresión
class Codificador:
    """Comprime el audio con Opus (como las llamadas de WhatsApp o Discord):
    unas 12 veces menos datos que el audio sin comprimir, casi igual calidad."""

    def __init__(self, bitrate=128_000):
        self.bitrate = bitrate
        self._clave = None

    def _preparar(self, rate, canales):
        import av
        layout = "stereo" if canales == 2 else "mono"
        self._resampler = av.AudioResampler(format="s16", layout=layout, rate=48000)
        self._fifo = av.AudioFifo()
        cc = av.CodecContext.create("libopus", "w")
        cc.sample_rate = 48000
        cc.layout = layout
        cc.format = "s16"
        cc.bit_rate = self.bitrate
        # lowdelay = modo de baja latencia; vbr off = tamaño constante, más parejo en la red
        cc.options = {"application": "lowdelay", "frame_duration": "20", "vbr": "off"}
        cc.open()
        self._cc, self._layout, self._rate, self._canales = cc, layout, rate, canales
        self._clave = (rate, canales)

    def codificar(self, pcm: bytes, rate: int, canales: int) -> list[bytes]:
        import av
        if self._clave != (rate, canales):
            self._preparar(rate, canales)
        datos = np.frombuffer(pcm, dtype=np.int16).reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(datos, format="s16", layout=self._layout)
        frame.sample_rate = rate
        for f in self._resampler.resample(frame):
            f.pts = None
            self._fifo.write(f)
        paquetes = []
        while self._fifo.samples >= 960:
            for paquete in self._cc.encode(self._fifo.read(960)):
                paquetes.append(bytes(paquete))
        return paquetes


# ---------------------------------------------------------------- servidor web
class Puente:
    def __init__(self):
        # cada cliente: (conexión, formato "opus" o "pcm")
        self.clientes: dict[web.WebSocketResponse, tuple] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self.bocinas = Bocinas()
        self.captura = Captura(self._desde_hilo)
        self.red = Red()
        self.codificador = Codificador()
        self.media = ControlMedia()

    # Llamado desde el hilo de audio
    def _desde_hilo(self, datos: bytes):
        if not (self.clientes and self.loop):
            return
        try:
            paquetes = self.codificador.codificar(datos, self.captura.rate, self.captura.canales)
        except Exception as e:
            print("  Error al comprimir:", e)
            paquetes = []
        self.loop.call_soon_threadsafe(self._difundir, datos, paquetes)

    def _difundir(self, pcm: bytes, paquetes: list[bytes]):
        for ws, (transporte, formato) in list(self.clientes.items()):
            if ws.closed:
                self.clientes.pop(ws, None)
                continue
            # Si la red del cliente va atrasada (más de ~0.5 s en cola), descartamos
            # este pedacito para que el retraso no se acumule
            limite = 8_000 if formato == "opus" else 96_000
            if transporte is not None and transporte.get_write_buffer_size() > limite:
                continue
            for mensaje in (paquetes if formato == "opus" else [pcm]):
                asyncio.ensure_future(ws.send_bytes(mensaje))

    def _actualizar_bocinas(self):
        if self.clientes:
            self.bocinas.silenciar()
        else:
            self.bocinas.restaurar()

    async def ws(self, request):
        ws = web.WebSocketResponse(heartbeat=10, max_msg_size=0)
        await ws.prepare(request)
        await ws.send_str(json.dumps({
            "tipo": "hola",
            "rate": self.captura.rate,
            "canales": self.captura.canales,
            "dispositivo": self.captura.nombre,
            "silenciar": self.bocinas.activo,
        }))
        formato = "opus" if request.query.get("formato") == "opus" else "pcm"
        transporte = request.transport
        try:  # mandar cada paquete en cuanto está listo, sin agruparlos
            transporte.get_extra_info("socket").setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass
        self.clientes[ws] = (transporte, formato)
        print(f"  iPhone conectado ({request.remote}, audio {formato}). Escuchando: {len(self.clientes)}")
        self._actualizar_bocinas()
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        orden = json.loads(msg.data)
                    except ValueError:
                        continue
                    if orden.get("tipo") == "silenciar":
                        self.bocinas.activo = bool(orden.get("valor"))
                        if not self.bocinas.activo:
                            self.bocinas.restaurar()
                        self._actualizar_bocinas()
                    elif orden.get("tipo") == "control":
                        accion = orden.get("accion")
                        resultado = await self.media.ejecutar(accion)
                        await ws.send_str(json.dumps({"tipo": "control", "accion": accion, **resultado}))
        finally:
            self.clientes.pop(ws, None)
            print(f"  iPhone desconectado. Escuchando: {len(self.clientes)}")
            self._actualizar_bocinas()
        return ws

    async def panel(self, request):
        return web.FileResponse(CARPETA / "panel.html")

    async def iphone(self, request):
        return web.FileResponse(CARPETA / "iphone.html", headers={"Cache-Control": "no-store"})

    async def qr(self, request):
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(self.red.url_ip, image_factory=qrcode.image.svg.SvgPathImage, box_size=12)
        buf = io.BytesIO()
        img.save(buf)
        return web.Response(body=buf.getvalue(), content_type="image/svg+xml",
                            headers={"Cache-Control": "no-store"})

    async def info(self, request):
        return web.json_response({
            "url": self.red.url_ip,
            "url_fija": self.red.url_fija,
            "dispositivo": self.captura.nombre,
            "escuchando": len(self.clientes),
        }, headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-store"})

    async def al_iniciar(self, app):
        self.loop = asyncio.get_running_loop()
        self.captura.iniciar()
        self.red.iniciar()

    async def al_cerrar(self, app):
        self.captura.detener()
        self.red.detener()
        self.bocinas.restaurar()
        for ws in list(self.clientes):
            await ws.close()


def ya_esta_corriendo() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PUERTO), timeout=0.5):
            return True
    except OSError:
        return False


def icono_bandeja():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=(47, 107, 255, 255))
    for x, alto in ((17, 14), (27, 26), (37, 34), (47, 18)):  # barritas de sonido
        d.rounded_rectangle((x - 3, 32 - alto // 2, x + 3, 32 + alto // 2), radius=3, fill="white")
    return img


def main_fondo(puente, app):
    """Corre sin ventana, con un ícono junto al reloj de Windows."""
    import pystray

    registro = Path(__file__).parent / "registro.txt"
    try:
        if registro.exists() and registro.stat().st_size > 1_000_000:
            registro.unlink()
    except OSError:
        pass
    sys.stdout = sys.stderr = open(registro, "a", encoding="utf-8", buffering=1)
    print(f"\n  --- Inicio {time.strftime('%Y-%m-%d %H:%M')} ---")

    loop = asyncio.new_event_loop()
    runner = web.AppRunner(app)

    def servir():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        loop.run_until_complete(web.TCPSite(runner, "0.0.0.0", PUERTO).start())
        print(f"  Listo en {puente.red.url_ip}  /  {puente.red.url_fija}")
        loop.run_forever()
        loop.run_until_complete(runner.cleanup())

    hilo = threading.Thread(target=servir, daemon=True)
    hilo.start()

    def salir(icono=None, item=None):
        try:  # devolver el sonido a la laptop y cerrar conexiones antes de apagar
            asyncio.run_coroutine_threadsafe(puente.al_cerrar(None), loop).result(timeout=5)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
        hilo.join(timeout=5)
        puente.bocinas.restaurar()
        icon.stop()

    puente.al_salir = lambda: threading.Thread(target=salir, daemon=True).start()

    def alternar_silencio(icono, item):
        puente.bocinas.activo = not puente.bocinas.activo
        if not puente.bocinas.activo:
            loop.call_soon_threadsafe(puente.bocinas.restaurar)
        loop.call_soon_threadsafe(puente._actualizar_bocinas)

    def texto_estado(item):
        n = len(puente.clientes)
        return "Escuchando en tu iPhone" if n == 1 else (f"{n} dispositivos escuchando" if n else "Esperando a tu iPhone")

    icon = pystray.Icon("puente_audio", icono_bandeja(), "Puente de Audio", menu=pystray.Menu(
        pystray.MenuItem(texto_estado, None, enabled=False),
        pystray.MenuItem("Mostrar código QR", lambda: webbrowser.open(f"http://localhost:{PUERTO}/"), default=True),
        pystray.MenuItem("Silenciar bocinas de la laptop", alternar_silencio,
                         checked=lambda item: puente.bocinas.activo),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Apagar Puente de Audio", salir),
    ))

    def refrescar():  # actualiza el texto del menú
        while hilo.is_alive():
            time.sleep(2)
            try:
                icon.title = f"Puente de Audio · {texto_estado(None)}"
                icon.update_menu()
            except Exception:
                pass

    threading.Thread(target=refrescar, daemon=True).start()
    icon.run()


def main():
    if ya_esta_corriendo():
        print("  El Puente de Audio ya está encendido (ícono junto al reloj).")
        if "--sin-navegador" not in sys.argv:
            webbrowser.open(f"http://localhost:{PUERTO}/")
        return

    puente = Puente()
    app = web.Application()

    async def apagar(request):  # solo desde esta misma laptop
        if request.remote not in ("127.0.0.1", "::1"):
            raise web.HTTPForbidden()
        if getattr(puente, "al_salir", None):
            puente.al_salir()
        return web.Response(text="Apagando")

    app.router.add_post("/apagar", apagar)
    app.router.add_get("/", puente.panel)
    app.router.add_get("/escuchar", puente.iphone)
    app.router.add_get("/ws", puente.ws)
    app.router.add_get("/opus-decoder.min.js", lambda r: web.FileResponse(
        CARPETA / "opus-decoder.min.js", headers={"Content-Type": "text/javascript; charset=utf-8"}))
    app.router.add_get("/qr.svg", puente.qr)
    app.router.add_get("/info", puente.info)
    app.on_startup.append(puente.al_iniciar)
    app.on_shutdown.append(puente.al_cerrar)  # primero: devolver el sonido y cerrar conexiones

    if "--fondo" in sys.argv:
        main_fondo(puente, app)
        return

    print()
    print("  ===============  PUENTE DE AUDIO  ===============")
    print(f"  En tu iPhone abre en Safari:  {puente.red.url_ip}")
    print(f"  Dirección fija (casa o hotspot): {puente.red.url_fija}")
    print("  (o escanea el código QR que se abrió en tu navegador)")
    print("  Para apagarlo cierra esta ventana o presiona Ctrl+C.")
    print("  =================================================")
    print()
    if "--sin-navegador" not in sys.argv:
        webbrowser.open(f"http://localhost:{PUERTO}/")
    web.run_app(app, host="0.0.0.0", port=PUERTO, print=None)


if __name__ == "__main__":
    main()
