# Sourcing review page: design record

Rebuilt 2026-10-29 evening after Sam rejected the first build (label/value cards, no images) as not
following the web app foundations. This file is the record the foundations ask for.

## Purpose, per user (foundations rule 11)

One user: Karen, a promo-products rep, looking at this page beside her Claude Code chat on a laptop
or on her phone.

- **What she decides here:** which supplier's product to quote, by weighing how the product looks
  (supplier photos) against what it costs landed in Hawaii and how much of that is freight; then
  which carrier service to put on the quote.
- **What the view presents:** her own words at the top, then one row per option, cheapest landed
  first, up to twenty: the supplier photos on the left; on the right the name, her cost each,
  catalog and setup, the three cheapest freight options with the carton facts and any carrier
  limits, what the price includes (with a link to the supplier when SAGE leaves it blank),
  decoration, colours, production, ship-from, carton, a price-break table and the goods, setup,
  freight bar; on the far right the landed cost per unit and the select button. Once she selects a
  product: every carrier option for it as a choice list, the quote details form, and a running
  quote summary with the Hawaii GE tax and per-unit figure.
- **What she does:** selects a product, selects a shipping method, enters the customer and her
  sell price, and builds the quote. The sheet is her own QUOTE layout, written by the quote
  tool, listed on the page with download and delete. Earlier runs are reachable from Sourcing runs.

Set in the grill-me with Sam, 2026-10-29; the pick-and-quote flow, the rows and the twenty options
added on his instruction the same evening. Recorded in `Brain/Decisions/log.md`.

## Mobbin references (rule 2)

Every region's reference is in the markup (`data-ref`, `data-took`) and the table under Provenance
at the end of this file is generated from it. The compare board additionally takes lululemon's iOS
compare (columns keep their width and scroll sideways on the phone) and Hims' tinted recommended
column; the header's single action placement follows Charma's feedback page. Those extra screens
are named inside the `data-took` text of the region they inform.

## Chart (dataviz method)

Stacked horizontal bar per candidate: goods, setup, freight, on one shared scale (the largest landed
total). Three categorical slots from the dataviz reference palette in fixed order, validated with
`validate_palette.js` on the white surface before use (result pasted in the commit message). 2 px
surface gaps between segments, 4 px rounded data end, legend once above the row, the total as the
only direct label, a hover title on each segment, and the same numbers in the attribute rows so
nothing is colour-only.

## Foundations rules applied

- 1, 7, 12 (sign-in), 16: not applicable, localhost tool with no accounts or session.
- 5, 6: nothing to set up; the page shows the latest run on open and the flow is one step at a
  time: select a product, choose shipping, fill the details, build.
- 8: no sign-out exists.
- 9: no feedback button. Recorded deviation (Sam, 2026-10-29): a local tool for one person, with no
  send path; she gives feedback in chat.
- 10: the line under each heading carries only facts that are not in the heading. Her prompt is the
  heading of the request block, set in regular weight because it runs past eight words.
- 11: purpose above.
- 12 (delete): every quote built on the page can be deleted from the Quotes built table; the
  server moves the file to `internal/Trash/Quotes/` and the row stays gone after a refresh.
- 13: focus rings are 2 px, offset, radius matched to the control, measured at both widths.
- 14: the one centred element, the empty state, is measured on both axes.
- 15: deleting a quote asks for confirmation in a dialog that names the file; Cancel and Escape
  do nothing; the server refuses a delete without `confirm: true`. Building a quote creates a
  local file and is not an external send.
- 17: the page has no free-text boxes; the quote details are single-line fields for names, phone,
  address and prices, so there is nothing to link.
- 18: `/favicon.svg`.
- 19: no eyebrow labels, pills or badge rows anywhere.
- 20: provenance in the markup, gated by `provenance_check.py` on the filled state, the empty
  state and the phone, 0 failing at the time of writing.
- House design rules: one action per column and per card, one colour per heading, headings lead
  every section, no motif copied from a reference. The visual system (white page, one sans,
  black and gray, gray product frames, black uppercase buttons) is lululemon's, matched rather
  than improved, per the website-builder skill's rule for reference builds.

## Not done

- Dark mode: the page is light only (colour-scheme light); dataviz's dark steps are not wired.
- Images are hot-linked from promoplace.com (SAGE's image host) and load without a session; if
  that host blocks her network the frame shows the product name instead.

## Provenance

<!-- provenance:start -->
Generated by `.claude/skills/website-builder/tools/provenance_check.py` from the `data-ref` attributes in the rendered DOM. Edit the markup, not this table.

| Region | Mobbin screen | What was taken |
|---|---|---|
| delete-dialog | https://mobbin.com/screens/11487039-8831-478a-9b3e-a5251899b5e5 | Mistral AI files: a confirm dialog that names the action, says what happens, and offers Cancel beside a red Delete |
| empty-state | https://mobbin.com/screens/48d4c1f0-8449-4370-be5b-fb96f887cdbb | Blue Apron Orders: a centred short heading with one line beneath saying when something will appear here |
| header | https://mobbin.com/screens/764af7f5-67bf-4b76-92f6-9a85e654efbe | lululemon site header on the Compare Products page: a slim white bar with a thin bottom rule, the brand name at the left and plain small navigation links beside it |
| header-nav | https://mobbin.com/screens/764af7f5-67bf-4b76-92f6-9a85e654efbe | lululemon site header: the row of plain small text links to the right of the brand, no underline until hover |
| layout | https://mobbin.com/screens/47a75aa6-fd83-4f88-b475-cde65f3384de | Urban Outfitters checkout: the shipping choice and details in a wide left column and the order summary in a narrower right column that stays in view; on the phone the summary follows the content |
| mobile-selection-bar | https://mobbin.com/screens/a05f6882-9983-41bb-a564-6a42b266bbd1 | Faire cart: a bar fixed to the bottom with the order total on the left and the one next-step button on the right, shown once something is selected |
| option-rows | https://mobbin.com/screens/1baaa795-1eb9-4596-9847-efaf5ba1a9e6 | GetYourGuide results list: one row per option with the photo on the left, the name and details in the middle, and the price on the right with a thin rule between rows; the product photo on a light gray frame and the black uppercase button are lululemon's https://mobbin.com/screens/764af7f5-67bf-4b76-92f6-9a85e654efbe |
| quote-details | https://mobbin.com/screens/6ee844eb-9b49-4f98-8c59-f8a27f7a6c9f | lululemon checkout: short labels above full-width inputs, two fields to a row, address lines beneath, with a note under a field when it needs one; the step heading is Uvodo's checkout https://mobbin.com/screens/6321f77a-c31a-44ac-991e-5ec24e589875 |
| quote-summary | https://mobbin.com/screens/47a75aa6-fd83-4f88-b475-cde65f3384de | Urban Outfitters Order Summary: a bordered card on the right with subtotal, shipping, tax and a bold total, and one full-width button to go on |
| quotes-list | https://mobbin.com/screens/e74f522b-aab3-40de-bb2f-0b6cd895f2b9 | Gusto Documents: a heading and a plain table of documents with the name and date on the left and the actions on the right of each row |
| request | https://mobbin.com/screens/76f16c95-05bd-4965-b5f9-3c55a5848dad | adidas search results: a small 'search for' line, the words searched in quotation marks as the big heading, and the result count beside it |
| run-history | https://mobbin.com/screens/9d9651df-1cba-449a-852d-d7d78e607f10 | Shop Search history: a left overlay panel with a round close button, a title, and one row per past search with a small product image, the words of the search and when it ran |
| run-history-panel | https://mobbin.com/screens/9d9651df-1cba-449a-852d-d7d78e607f10 | Shop Search history: the panel itself, rounded, pinned to the left edge with the close button at its top |
| shipping-options | https://mobbin.com/screens/efd7feb8-458f-4bda-89e9-7834bb76729f | PayPal Shipping Rates: a heading, one sentence, then one bordered card per carrier service with the service name, the delivery line under it and the price on the right; the chosen card is tinted with a strong border. The step heading with a check when done is Uvodo's checkout https://mobbin.com/screens/6321f77a-c31a-44ac-991e-5ec24e589875 |
<!-- provenance:end -->
