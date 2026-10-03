# Digi integration

This owner fork includes a tested Digi adapter and sidebar globe. The installed
copy lives in `/home/digi070/Work/digi`; this directory preserves its integration
assets without personal data or credentials.

- `gods_eye.py`: loopback MCP query/control adapter, targeted ADS-B fallback,
  current browser-camera observations and honest flight reporting.
- `static/`: sidebar view and scripts.
- `digi-hooks.patch`: changes to Digi’s app and unified sidebar composition,
  relative to the October 3, 2026 pre-integration version. Review before applying
  to a different Digi release; it is not a complete standalone Digi application.
- `test_gods_eye.py`: adapter regression tests for Digi’s unittest suite.
- `install-service.py`: installer for the owner’s existing local paths and
  Node 26.7.0 runtime. It does not install dependencies or build assets itself.

`src/app/embed.js` additionally supports `?embed=1&controls=1` for manual full
controls and emits `gev:camera` messages to the parent on camera movement.
The service allows framing only by Digi’s loopback origins.

Install dependencies with `PUPPETEER_SKIP_DOWNLOAD=1 npm ci`, run `npm run build`,
then install the user service. Port 4173 supplies the globe and MCP transport;
Digi at port 8765 mediates agent queries and authenticated browser observations.
Optional photorealistic 3D provider keys are configured in the full app.

See `OPERATIONS.md` for the installed behavior, data-source limits and validation.
