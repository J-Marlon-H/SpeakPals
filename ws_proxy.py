"""
WebSocket proxy: browser → this server → ElevenLabs Scribe v2 Realtime
Keeps the ElevenLabs API key server-side (browsers can't set custom headers on WS).
"""
import asyncio
import json
import base64
import os
import ssl
import websockets
from dotenv import load_dotenv

load_dotenv("keys.env")
ELEVEN_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
EL_WS_BASE  = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
PROXY_PORT  = 8502


async def proxy(browser_ws):
    qs   = browser_ws.request.path if hasattr(browser_ws, "request") else ""
    lang = "en" if "lang=en" in qs else "da"
    el_url = (
        f"{EL_WS_BASE}"
        f"?model_id=scribe_v2_realtime"
        f"&language_code={lang}"
        f"&encoding=pcm_s16le"
        f"&sample_rate=16000"
    )

    # Disable TLS verification — corporate networks often replace certificates
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(
            el_url,
            additional_headers={"xi-api-key": ELEVEN_KEY},
            ssl=ssl_ctx,
            ping_interval=20,
            open_timeout=10,
        ) as el_ws:

            async def browser_to_el():
                async for msg in browser_ws:
                    try:
                        if isinstance(msg, bytes):
                            if len(msg) < 2:
                                continue
                            await el_ws.send(json.dumps({
                                "message_type": "input_audio_chunk",
                                "audio_base_64": base64.b64encode(msg).decode(),
                                "commit": False,
                                "sample_rate": 16000,
                            }))
                        else:
                            data = json.loads(msg)
                            if data.get("type") == "commit":
                                await el_ws.send(json.dumps({
                                    "message_type": "input_audio_chunk",
                                    "audio_base_64": "",
                                    "commit": True,
                                    "sample_rate": 16000,
                                }))
                    except websockets.ConnectionClosed:
                        break

            async def el_to_browser():
                async for msg in el_ws:
                    try:
                        await browser_ws.send(msg)
                    except websockets.ConnectionClosed:
                        break

            await asyncio.gather(browser_to_el(), el_to_browser())

    except Exception as e:
        try:
            await browser_ws.send(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass


async def _run():
    async with websockets.serve(proxy, "localhost", PROXY_PORT):
        await asyncio.Future()


def start_in_thread():
    """Call once from Streamlit; runs proxy in a daemon thread."""
    import threading
    loop = asyncio.new_event_loop()

    def _target():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())

    t = threading.Thread(target=_target, daemon=True, name="ws-proxy")
    t.start()
    return t
