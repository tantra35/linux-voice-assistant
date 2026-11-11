#!/bin/bash
# Client-only image vs host server (mounted socket): mpv playback via pipewire AND pulse drivers
set -u
fail=0
export XDG_RUNTIME_DIR=/run/user/1000
echo "=== pactl info against HOST server ==="
if pactl info >/dev/null 2>&1; then echo "ok: pactl info works"; else echo "FAIL: pactl info"; fail=1; fi
pactl load-module module-null-sink >/dev/null 2>&1 && echo "ok: null sink loaded"
sleep 1

echo "=== dpkg sanity ==="
dpkg -l | grep -E '^ii +pipewire ' && { echo "FAIL: pipewire pkg present"; fail=1; } || echo "ok: no pipewire daemon pkg"
ls /usr/share/pipewire/client.conf >/dev/null 2>&1 && echo "note: client.conf present" || echo "note: client.conf ABSENT (client runs on libpipewire defaults)"

echo "=== mpv playback via HOST server (both drivers) ==="
out=$(.venv/bin/python - <<'EOF'
import numpy as np, wave, time
import mpv
rate = 44100
t = np.linspace(0, 2, 2 * rate)
data = (np.sin(2 * np.pi * 440 * t) * 32000).astype(np.int16)
with wave.open('/tmp/tone.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(data.tobytes())

def play(device):
    errors = []
    p = mpv.MPV(log_handler=lambda l, pre, txt: errors.append(txt.strip()) if l in ('error','fatal') else None)
    p['audio-device'] = device
    p.play('/tmp/tone.wav')
    eof = False
    for _ in range(200):
        try:
            if p['eof-reached']:
                eof = True; break
        except Exception: pass
        time.sleep(0.1)
    p.terminate()
    print('%s: eof=%s errors=%r' % (device, eof, errors))

play('pipewire')
play('pulse')
EOF
)
echo "$out"
case "$out" in
  *"pipewire: eof=True errors=[]"*) echo "ok: pipewire driver plays via host server";;
  *) echo "FAIL: pipewire driver"; fail=1;;
esac
case "$out" in
  *"pulse: eof=True errors=[]"*) echo "ok: pulse driver plays via host server";;
  *) echo "FAIL/NOTE: pulse driver";;
esac

exit $fail
