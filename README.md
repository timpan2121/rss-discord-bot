# RSS → Discord

Varje flöde postar till en egen kanal via en Discord-webhook. Körs var 10:e minut på GitHub Actions.

## Lägga till ett flöde
1. Discord: Kanalinställningar → Integrationer → Webhooks → Ny webhook → Kopiera URL.
2. GitHub: Settings → Secrets and variables → Actions → New repository secret, t.ex. `WEBHOOK_GP`.
3. Lägg till i `feeds.json`: `{ "name": "GP", "url": "https://…/rss", "webhook_secret": "WEBHOOK_GP" }`
4. Lägg till `WEBHOOK_GP: ${{ secrets.WEBHOOK_GP }}` under `env:` i `.github/workflows/rss.yml`.

Ett nytt flöde postar sina 3 senaste inlägg vid första körningen, resten räknas som sedda.

Valfritt per flöde: `"interval": 60` (minuter mellan kontroller) och `"interval_sunday": 10` (söndagar). Utan dessa kontrolleras flödet varje varv (var 5:e minut).

Filtrering: `"keywords": ["vallentuna", …]` postar bara poster där något ord finns i rubrik/ingress/länk. Sidor utan RSS: `"link_pattern": "/[a-z]+/[a-z0-9-]+/\\d+"` läser artikellänkar från sidan och hämtar rubrik/ingress/bild från artikelns og-taggar. `"exclude": ["regex", …]` tar bort poster där rubrik + " | " + ingress matchar.

Profilbild: `"avatar": "avatars/namn.png"` (fil i repot) eller en full URL.
