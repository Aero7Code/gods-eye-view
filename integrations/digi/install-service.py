from pathlib import Path
import subprocess
home=Path.home()
unit=home/'.config/systemd/user/digi-gods-eye.service'
unit.parent.mkdir(parents=True,exist_ok=True)
unit.write_text('''[Unit]
Description=God's Eye View live resource for Digi
After=network.target
[Service]
Type=simple
WorkingDirectory=/home/digi070/Work/gods-eye-view
ExecStart=/home/digi070/.local/share/mise/installs/node/26.7.0/bin/node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4173 --strictPort
Environment=HOST=127.0.0.1
Environment=PORT=4173
Environment="GEV_EMBED_FRAME_ANCESTORS=http://127.0.0.1:8765 http://localhost:8765"
Restart=on-failure
RestartSec=5
UMask=0077
NoNewPrivileges=true
[Install]
WantedBy=default.target
''')
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','enable','--now','digi-gods-eye.service'],check=True)
