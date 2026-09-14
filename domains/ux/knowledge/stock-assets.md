# Stock Asset Resolution — Free-Rights Provider Chain (R3)

> Single source of truth for resolving third-party photography / iconography with
> verifiable licence provenance. The download itself is executed by the agent
> (HTTP or MCP), never by the `che` runtime; `che designer stock add` only records
> provenance once a real image has been validated.

## Provider chain (try in this order — never skip)

1. **Real Unsplash photo URL (GUARANTEED free-rights)** — `https://images.unsplash.com/photo-<ID>?auto=format&fit=crop&w=1024&h=1024&q=90`.
   - Mandatory headers: `User-Agent: Mozilla/5.0`, `Accept: image/webp,image/jpeg,*/*`.
   - Do NOT use `source.unsplash.com` (deprecated → returns HTML 403).
   - Validate magic bytes `ffd8ff` (JPEG) or `89504e47` (PNG), size > 80KB.
   - `provider=unsplash`, `license=Unsplash License` (free to use commercially, no attribution required but appreciated), `source_url=<the photo URL>`.
2. **text_to_image endpoint** — `https://coresg-normal.trae.ai/api/ide/v1/text_to_image?prompt=<ENCODED>&image_size=square_hd|portrait_16_9`.
   - MANDATORY validation: photo MD5 differs from others; unique colours > 25,000; raw bytes contain no `The image is generating` or `refresh page` substring.
   - `provider=text_to_image`, `license=generated` (model output, no third-party rights), `source_url=<the endpoint URL>`.
3. **OpenPencil `stock_photo` MCP** — applies a query to a rectangle leaf via JSON array requests (`query` + `orientation=square`).
   - `provider=openpencil_stock_photo`, `license=verify-per-provider`, `source_url=<resolved image URL>`.
4. **Pillow/ImageMagick offline fallback** — paste a previously downloaded photo over a rendered canvas base. Never fails, but is derived from provider 1 or 2, so provenance still traces to that upstream provider.

## Provenance contract (INV-3)

Every third-party asset under `design/assets/` MUST have a matching line in
`design/assets/CREDITS.md` containing all three fields before it is referenced by
any deliverable:

```text
- <filename> | provider=<provider> | license=<license> | source_url=<url>
```

## Rejection rule (AB-4)

If a provider returns an HTML error page / 403 / placeholder payload instead of
image bytes, the payload MUST be discarded: no file is written under
`design/assets/` and no entry is appended to `CREDITS.md`. The pipeline advances
to the next provider and reports the failed provider on stderr.

`che designer stock add` enforces this via magic-byte inspection (rejects
`<!DOCTYPE`, `<html>`, `<head>`, `<body>`, `<title>` prefixes and any non-image
signature) before writing anything.
