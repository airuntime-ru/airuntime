# Landing simplify — notes

## Structure (6 sections)
1. Hero + simplified ProcessDemo
2. Result (site + bot + trust strip)
3. How it works (3 static steps)
4. Use cases (4 static)
5. Trust (merged infra/versions/security + audience one-liner)
6. FAQ (5) + Final CTA

## Removed sections
- Comparison
- Infra (standalone)
- Versions timeline
- Security (standalone)
- Audience cards

## Client → server
Kept client: `site-header`, `process-demo`, `faq-accordion`
Server: hero, result, how-it-works, use-cases, trust, faq shell, final-cta, footer
Removed framer-motion from landing demo/how-it-works

## Checks
- `tsc --noEmit` OK
- eslint landing OK
- `npm run build` OK

## Lighthouse (local prod `next start`, desktop emulation)
Measured after simplify (no prior baseline in this session):

| Category | Score |
|---|---|
| Performance | 66 |
| Accessibility | 96 |
| Best Practices | 100 |
| LCP | 4.0 s |
| CLS | 0 |

Performance is below the ≥90 goal on this machine/run (cold headless Chrome against localhost). Accessibility and CLS meet targets. Re-check on a warm CDN/prod deploy before treating Perf as final.

Screenshots (gitignored PNGs under `docs/landing-audit/`):
- `simplify-desktop.png`
- `simplify-mobile.png`
- `simplify-desktop-full.png`
