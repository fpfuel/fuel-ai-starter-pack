---
name: images
description: Make or change pictures with KIE.ai, Nano Banana 2. Use when Karen asks for an image, a mockup, a picture, a graphic, a social post or a flyer, or says "put this logo on", "show the customer what it looks like", "make a picture of".
---

# Images

Runs on her own KIE.ai account and credits. If `python .agents/skills/images/tools/kie_image.py check`
says there is no key, run the images step of `/setup` (9b).

## Make one

1. Get what she wants in a sentence or two: what it shows, where it will be used (email to a
   customer, Instagram, a flyer), and any words that must appear.
2. References, if any: a logo or photo she points to, or a product picture from a sourcing run
   (the candidate's `imageUrl` in `internal/Domains/Work/ASB/sourcing/<run>.json`). Up to 10.
3. Write the prompt in plain description: the subject, the setting, the light, the angle, the
   exact wording in quotes, and "no other text, no watermark". For a logo on a product, say which
   reference is the logo and which is the product, and where the logo goes.
4. Run:
   `python .agents/skills/images/tools/kie_image.py make --prompt "..." [--ref FILE_OR_URL ...]
   [--aspect 1:1|4:5|16:9|9:16|3:4|4:3] [--size 1K|2K] [--name short-name]`
   Default 1K square, about 4 cents. 2K for print, about 16 cents. It waits about a minute and
   saves to `External/Images/`.
5. Look at the picture before showing her: wrong or garbled words, a changed logo, extra text.
   If something is off, say what and offer one retry with a fixed prompt. Never retry in a loop.
6. Give her the file path and the credits it used.

## Notes

- A mockup is a sketch for the customer, not a proof: say so when it goes in a quote email.
- Only her customers' own logos and her own brand, or plain generic products.
- Pictures stay on her computer. KIE deletes its copy after 14 days and uploaded references
  after a day.
