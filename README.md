# RSS → Discord

Varje flöde postar till en egen kanal via en Discord-webhook. Körs var 10:e minut på GitHub Actions.

## Lägga till ett flöde
1. Discord: Kanalinställningar → Integrationer → Webhooks → Ny webhook → Kopiera URL.
2. GitHub: Settings → Secrets and variables → Actions → New repository secret, t.ex. `WEBHOOK_GP`.
3. Lägg till i `feeds.json`: `{ "name": "GP", "url": "https://…/rss", "webhook_secret": "WEBHOOK_GP" }`
4. Lägg till `WEBHOOK_GP: ${{ secrets.WEBHOOK_GP }}` under `env:` i `.github/workflows/rss.yml`.

Ett nytt flöde markerar befintliga inlägg som sedda vid första körningen (ingen spam).
