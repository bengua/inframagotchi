# inframagotchi avatars

The default renderer is the manga stray cat in `web/index.html`.

This project also ships a few alternate canvas avatars under `web/avatars/`.
They are all drawn in code (HTML5 canvas + plain JS), keep the same decoupled
contract (`window.setHealth(pct)`), and degrade as health drops. Pick one by
setting the top-level `avatar` key in `inframagotchi.json`.

```json
{
  "avatar": "avatars/dog.html",
  "probe": [
    { "type": "disk", "path": "/", "interval": 5 }
  ]
}
```

The value is a path relative to the `web/` root. Changing the avatar requires
restarting the app; the live config editor reloads probes but does not switch
the renderer window.

## Available avatars

| Avatar   | File                         | Canvas size | Notes |
|----------|------------------------------|-------------|-------|
| Dog      | `web/avatars/dog.html`       | 420 × 470   | Floppy ears, wagging tail, tongue pants when healthy and droops when failing. |
| Goldfish | `web/avatars/fish.html`      | 360 × 430   | Swims in a bowl; slows down, lists, and "belly up" as health drops. |
| Hamster  | `web/avatars/hamster.html`   | 360 × 380   | Cheeks pulse with load; collapses in a fluffy heap at 0 %. |
| Llama    | `web/avatars/llama.html`     | 320 × 420   | Long neck, judgmental expression, spits the monitor when critical. |
| Offline  | `web/avatars/offline.html`   | 420 × 470   | Not a health avatar — a tombstone screen shown when the engine is unreachable. |

## Preview views

These screenshots are committed under `docs/avatars/previews/` as documentation
assets, under the explicit exception to the usual "zero bundled images" rule.

### Goldfish

![Goldfish avatar](previews/fish.png)

### Hamster

![Hamster avatar](previews/hamster.png)

### Llama

![Llama avatar](previews/llama.png)

### Offline / tombstone

![Offline state](previews/offline.png)

## Adding a new avatar

1. Create a self-contained HTML file under `web/avatars/`.
2. Render through a single canvas and expose `window.setHealth(pct)` so the
   engine can push health updates.
3. Keep the slider as a manual/demo override, like the default cat renderer.
4. Update this file and `README.md` so users can discover it.
