#!/bin/bash
# Verify no-pipewire-daemon image: daemon pkgs gone, client libs + mpv intact
set -u
fail=0

echo "=== 1. pipewire daemon packages absent ==="
dpkg -l | grep -E '^ii +(pipewire|pipewire-bin|pipewire-alsa|pipewire-pulse) ' && { echo "FAIL: daemon pkgs present"; fail=1; } || echo "ok: pipewire/pipewire-bin/pipewire-alsa/pipewire-pulse not installed"
command -v pipewire >/dev/null 2>&1 && { echo "FAIL: pipewire binary present"; fail=1; } || echo "ok: no pipewire binary"
command -v pw-cli >/dev/null 2>&1 && { echo "FAIL: pw-cli present"; fail=1; } || echo "ok: no pw-cli"
ls /usr/lib/*/alsa-lib/libasound_module_pcm_pipewire.so >/dev/null 2>&1 && { echo "FAIL: pipewire alsa plugin present"; fail=1; } || echo "ok: no alsa->pipewire plugin"

echo "=== 2. client libs (libmpv2 deps) present ==="
ldconfig -p | grep -E 'libpipewire-0.3.so.0|libspa' | head -3
ldd /usr/lib/x86_64-linux-gnu/libmpv.so.2 2>/dev/null | grep -c pipewire

echo "=== 3. mpv loads and its pipewire driver is registered ==="
.venv/bin/python - <<'EOF'
import mpv
p = mpv.MPV()
print('DRIVERS:', sorted({d['name'].split('/')[0] for d in p.audio_device_list}))
p.terminate()
EOF

echo "=== 4. in-container server still possible on demand (daemon reinstall restores it) ==="
apt-get update -qq >/dev/null 2>&1
apt-get install -y --no-install-recommends pipewire pipewire-bin pipewire-pulse >/dev/null 2>&1 && echo "reinstalled daemon pkgs"
export XDG_RUNTIME_DIR=/run/user/1000
mkdir -p "$XDG_RUNTIME_DIR"
pipewire >/tmp/pw.log 2>&1 &
pipewire-pulse >/tmp/pwpulse.log 2>&1 &
for i in $(seq 1 20); do pactl info >/dev/null 2>&1 && break; sleep 1; done
pactl info >/dev/null 2>&1 && echo "ok: pactl info works after daemon reinstall" || { echo "FAIL: pactl info"; fail=1; }
pactl load-module module-null-sink >/dev/null
out=$(.venv/bin/python - <<'EOF'
import numpy as np, wave, time
import mpv
rate = 44100
t = np.linspace(0, 2, 2 * rate)
data = (np.sin(2 * np.pi * 440 * t) * 32000).astype(np.int16)
with wave.open('/tmp/tone.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
    w.writeframes(data.tobytes())
errors = []
p = mpv.MPV(log_handler=lambda l, pre, txt: errors.append(txt.strip()) if l in ('error','fatal') else None)
p['audio-device'] = 'pipewire'
p.play('/tmp/tone.wav')
eof = False
for _ in range(200):
    try:
        if p['eof-reached']:
            eof = True; break
    except Exception: pass
    time.sleep(0.1)
print('eof=%s errors=%r' % (eof, errors))
EOF
)
echo "$out"
case "$out" in *"eof=True"*"errors=[]"*) echo "ok: pipewire-driver playback to EOF";; *) echo "FAIL: playback"; fail=1;; esac

exit $fail
