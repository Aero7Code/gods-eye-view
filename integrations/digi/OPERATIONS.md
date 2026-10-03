# God’s Eye View in Digi

Installed October 3, 2026 from upstream v0.2.1, commit aa16b7c.
Owner fork: https://github.com/Aero7Code/gods-eye-view.
Source: `~/Work/gods-eye-view`; Digi adapter: `digi/gods_eye.py`.

Open **God’s Eye View** in Digi’s sidebar. Search for a place, pan and zoom,
switch to **Full controls**, or open the full app separately. The globe loads
only when the sidebar view is opened. Enable flight refresh to repeat your flight
lookup every 30 seconds while the panel is visible. The globe’s own aircraft layer
refreshes independently. Flight reports, observed path points and source evidence
are available below the globe. **Explore live resources** lists the available
queries with their actual input schemas.

Say or type:

- “Hey Digi, show me Paris, France.”
- “Hey Digi, where is Southwest flight 2456?”
- “Where is flight WN2456?”
- “What aircraft are around this area?”
- “Show me the earthquakes near Tokyo.”

Place and identifiable flight commands have direct local routing. Other regional
questions use Digi’s `gods_eye` tool: `catalog` supplies query schemas, `query`
executes one, `flight` retrieves a flight report, and `state` supplies the selected
view and the latest browser camera observation. Browser camera observations let
Digi use the area you manually pan to. They are ephemeral, retained only in memory;
when the browser is absent, Digi has no live browser observation.

## Data and limits

The existing God’s Eye View MCP catalog supplies 29 public-resource tools, including
aircraft, recent tracks, route enrichment, ships, satellites, earthquakes,
weather maps, public cameras, infrastructure and situation briefs. Coverage,
provider keys, quotas and freshness vary by tool. Missing or stale information
is reported rather than invented. A source URL or camera image does not guarantee
that Digi’s language model visually inspected it.

Flight numbers WN2456, SWA2456 and Southwest 2456 map to callsign SWA2456.
A2456 alone is ambiguous; the owner’s example with “south west” resolves to SWA2456.
When the global anonymous feed is stale or has no match, Digi uses a targeted
`api.adsb.lol/v2/callsign/...` lookup. Report timestamps must be fresh and valid.

A flight report includes reported coordinates, altitude, speed, source timestamp,
route metadata when available and recent observed track points. A simplified
observed track is drawn on the globe; it is not the future flight plan. Route
metadata from adsbdb can describe another leg or an older usual route. If it
conflicts with a known low-altitude departure track, arrival estimates are
suppressed. Otherwise distance and time are explicitly hypothetical to the
metadata destination: great-circle distance divided by current ground speed.
They are not confirmed airline arrival times and exclude turns, weather and landing.
Confirmed destinations and operational airline ETAs require a suitable additional
schedule/flight-status provider; no paid provider was subscribed to.

The default map uses keyless Esri imagery and terrain. Photorealistic 3D building
tiles need optional Cesium ion or Google provider configuration in the full app;
these keys are not needed for the installed basic globe or public flight feeds.

## Operation and recovery

`digi-gods-eye.service` is enabled at user login, binds only to 127.0.0.1:4173,
and runs the production build with the project’s API middleware. Digi remains at
127.0.0.1:8765. Framing is enabled only for Digi’s loopback origins. Digi API calls
retain existing authentication and same-origin controls. Tokens, database files,
provider credentials and personal conversations are not included in the fork.

```bash
systemctl --user status digi digi-gods-eye
systemctl --user restart digi-gods-eye
journalctl --user -u digi-gods-eye -n 40 --no-pager
```

Rebuild after editing God’s Eye View: `cd ~/Work/gods-eye-view && npm run build`,
then restart its service. No automatic upstream update overwrites this integration.
The local clone has `origin` pointing to the owner fork and `upstream` to the
original repository. Integration assets and the Digi hook patch are saved under
`integrations/digi/` in the fork.

Pre-integration Digi hook files are in `~/Work/digi-gods-eye-backup`. The guardian
recovery snapshot is updated to include the installed adapter. The existing Digi
model, conversations and database have not been migrated.

## Verification

Digi application regression tests: 35 passed. Unified typed/voice conversation
regressions: 6 passed. Adapter tests cover callsign normalization, command routing,
MCP results, stale/missing positions, targeted lookup timestamps, bounded browser
observations and conflicting route metadata. Chromium checks confirm Paris camera
coordinates and loaded imagery, embedded rendering, full controls, actual camera
observations and no JavaScript page errors. Both original example requests were
checked through Digi’s live temporary-chat endpoint.
