# Style archetypes: a study for the style warm-up

The outfit taste model (`closet/taste.py`) learns *what* someone likes: relaxed tops, one pop of colour, knitwear. This study adds *which style worlds* they are drawn to, so the oni can say "you're mostly minimalist with a dark academia streak" and help them grow towards a style they love but don't wear yet, using clothes they already own first.

**How the app uses it:**
- Each style becomes a Pinterest-style board of 6–7 pieces. Muse Image draws each piece, and SAM 3.1 cuts it out like a scanned garment.
- The warm-up shows two boards at a time.
- A Bradley–Terry model learns one weight per style and asks next about the pairs it is least sure of.
- Each style also has a profile on the taste model's 20 outfit features. That means:
  - a board pick teaches the outfit model too
  - your real closet can be read in the same terms

**Method.** These are summaries of recurring, cross-checked descriptions from fashion media, fashion history writing and retailer style guides (sources at the end). Where sources disagreed or were thin, only the consensus is kept, and the doubts are noted. Styles are fuzzy social categories, not rules: the profiles are a starting point the model corrects from each person's own picks.

---

## Quick map

Four axes separate the styles best, and they are also what the outfit features can see:

| Style | Formality | Darkness | Volume | Colour |
|---|---|---|---|---|
| Streetwear | Casual, sporty | Mixed | Oversized top, roomy bottom | Neutral base, bold graphics |
| Dark academia | Smart casual | Dark, warm | Tailored, layered | Browns, burgundy, forest green |
| Cyberpunk / techwear | Technical | Very dark, cool | Fitted base, technical layers | Black, one neon accent |
| Gothic | Dressed up | Black | Dramatic, long | Black; deep red or purple |
| Brutalist | Avant-garde | Dark, monochrome | Oversized, draped, sculptural | Monochrome |
| Parisian chic | Smart casual | Light/dark contrast | Slim, simple | Navy, cream, one red note |
| Soft | Casual, sweet | Light | Cosy, cropped knits | Pastels |
| Minimalist | Smart casual | Neutral | Clean, straight | Black, white, grey, beige |
| Y2K | Playful | Light, bright | Low-rise, cropped, flared | Pinks, silver, colour mixing |
| Gorpcore | Sporty, technical | Mixed | Layered, roomy | Earthy base, one bright shell |
| Old money | Smart | Warm neutrals | Tailored, relaxed | Cream, navy, camel |
| Grunge | Casual, undone | Dark-ish, faded | Oversized, layered | Plaid, black, faded denim |

**Neighbours, which blend easily:**
- dark academia ↔ old money (tailoring and knits, one darker than the other)
- gothic ↔ brutalist ↔ cyberpunk (black on black)
- streetwear ↔ Y2K ↔ gorpcore (casual, sporty, graphic)
- minimalist ↔ Parisian chic ↔ old money (clean, neutral, quality)
- grunge ↔ streetwear (oversized, band tees, denim)

**Opposites, which make the most informative warm-up pairs:**
- soft ↔ gothic
- gorpcore ↔ old money
- minimalist ↔ Y2K

The model finds these on its own: they are the pairs whose outcome it is least sure of early on.

---

## Streetwear (ストリート)

- **Origins:** Southern California in the late 1970s and 80s, out of skate and surf culture. It grew through hip-hop and punk, then went global through limited drops and sneaker culture. The eras show in the silhouette:
  - 90s: baggy jeans, graphic hoodies, snapbacks
  - 2000s: big logos, high-tops, trucker hats
  - 2010s: oversized hoodies, chunky "dad" sneakers
  - 2020s: wide cargo pants, platform sneakers
- **Essence:** comfort and identity. What you wear signals which scene you belong to.
- **Palette:** a black, white and grey base, with colour carried by graphics and sneakers.
- **Silhouette:** oversized on top, roomy or tapered below. The volume is the point.
- **Fabrics:** heavyweight cotton jersey and fleece, nylon, denim.
- **Key pieces:** graphic tee, hoodie, varsity or coach jacket, cargo pants, baggy jeans.
- **Shoes:** sneakers are the anchor: retro basketball, Dunks or AF1-style, New Balance.
- **Accessories:** baseball cap, sling bag, chunky silver chain.
- **Borrow it from your closet:** your roomiest hoodie or tee, with your widest trousers and your chunkiest sneakers.
- **App profile:** relaxed top, wide bottom, sporty, print, high contrast. Smart pieces and slim trousers count against it.

## Dark academia (ダークアカデミア)

- **Origins:** an online aesthetic of the mid-2010s, built on campus novels, gothic architecture and the old Ivy League preppy tradition of the 1920s and 30s. It romanticises study and old libraries.
- **Essence:** scholarly, moody, tactile, slightly melancholy.
- **Palette:** deep browns, charcoal, burgundy, forest green, navy and black, with cream shirting and gold as accents.
- **Silhouette:** tailored but relaxed. Layering (shirt, knit, blazer, coat) is the signature.
- **Fabrics:** wool, tweed, corduroy, cashmere, velvet, crisp cotton shirting. The texture is half the look.
- **Key pieces:** tweed blazer, knit vest or cable sweater, turtleneck, pleated trousers or plaid skirt, long wool coat.
- **Shoes:** leather loafers or lace-up Oxfords.
- **Accessories:** leather satchel, round tortoiseshell glasses, a vintage watch.
- **Borrow it from your closet:** a knit over a collared shirt, in browns and darks, with your smartest trousers.
- **App profile:** knit, smart, layered, warm tones, tonal, low contrast. Sporty pieces and loud colour mixing count against it.

## Cyberpunk / techwear (サイバー)

- **Origins:** sci-fi (*Blade Runner*, *Ghost in the Shell*, *Cyberpunk 2077*) meets real technical outdoor and military clothing. Techwear is the wearable, functional branch.
- **Essence:** function as costume, built for an imagined dystopian city.
- **Palette:** black and greys dominate, with one cold neon or reflective accent.
- **Silhouette:** a fitted or semi-fitted base under technical layers, with tapered legs.
- **Fabrics:** waterproof-breathable shells (Gore-Tex type), nylon, neoprene, leather or PVC, reflective trims.
- **Key pieces:** shell jacket, technical base layer, tapered cargo pants with straps.
- **Shoes:** chunky tactical high-tops or boots.
- **Accessories:** chest rig or sling bag, harnesses and utility belts, wraparound shades, gloves, chokers.
- **Borrow it from your closet:** all black, your most technical jacket, slim cargos, and a crossbody bag worn high.
- **App profile:** all dark, layered, tonal, sporty, cool tones, slim bottom. Warm tones and prints count against it.

## Gothic (ゴシック)

- **Origins:** the post-punk music scene of the late 1970s and 80s, steeped in Gothic literature and Victorian mourning dress. It has many sub-styles, from Victorian-inspired trad goth to deathrock and cyber goth, and is famously individual.
- **Essence:** dark romance and drama.
- **Palette:** black, with deep red, purple and sometimes white as accents.
- **Silhouette:** long and dramatic: long coats, wide or flared legs, high collars.
- **Fabrics:** velvet, lace, brocade, chiffon, leather. Opulent fabrics against hard metal.
- **Key pieces:** velvet or lace blouse, long leather or wool coat, black wide trousers or long skirt.
- **Shoes:** platform or buckled combat boots.
- **Accessories:** silver jewellery (crosses and rings), lace choker, small structured black bag. Our sources didn't pin silver as essential; it is the common convention.
- **Borrow it from your closet:** all black with one rich texture (velvet, lace or leather) and your heaviest boots.
- **App profile:** all dark, tonal, layered, a little smart. Sporty pieces and colour mixing count against it.

## Brutalist (ブルータリスト)

- **Origins:** a fashion borrowing from brutalist architecture: raw concrete, repeated forms, structure on show. Rick Owens and his DRKSHDW line are the main reference: elongated, draped, raw-edged, heavyweight. Margiela is its intellectual cousin, deconstructing where Owens rebuilds.
- **Essence:** clothes as structure. Severe, sculptural, uncompromising.
- **Palette:** monochrome: black, greys, sometimes concrete or dust tones.
- **Silhouette:** extreme proportions: dropped crotches, wide legs, boxy or draped tops, long lines.
- **Fabrics:** heavy jersey, leather, wool, unfinished edges.
- **Key pieces:** draped asymmetric top, boxy oversized coat, wide dropped trousers.
- **Shoes:** chunky square-toe boots and heavy soles.
- **Accessories:** sculptural metal cuffs, angular shades, geometric bags.
- **Borrow it from your closet:** one colour head to toe, with the boxiest top over the widest trouser. Let volume do the work.
- **App profile:** tonal, wide bottom, all dark, relaxed top, layered. Prints and colour mixing count against it.
- **Note:** there is no settled definition of "brutalist fashion". Most writing is descriptive, so this profile is deliberately broad.

## Parisian chic (パリシック)

- **Origins:** the enduring idea of the effortless French wardrobe, built from a few staples worn on repeat.
- **Essence:** looking put-together without looking like you tried.
- **Palette:** navy, cream, black and denim, with one red note (lips, scarf or bag).
- **Silhouette:** simple and slim: straight jeans, a neat top, a coat that skims the body.
- **Fabrics:** cotton, denim, wool, silk.
- **Key pieces:** the trench coat (named the number one staple again and again), a Breton striped top, straight dark jeans, a tailored blazer.
- **Shoes:** ballet flats or loafers.
- **Accessories:** basket bag, silk scarf, cat-eye sunglasses.
- **Borrow it from your closet:** a striped top with your best jeans, a light coat, and one red thing.
- **App profile:** one pop, high contrast, denim, slim bottom, mixing casual and smart, a stripe. Sporty pieces count against it.

## Soft (ソフト)

- **Origins:** the TikTok-era "soft girl" and "soft boy" looks, gentle and cute, with roots in Japanese kawaii and K-fashion.
- **Essence:** cosy and sweet. Nothing harsh.
- **Palette:** pastels (pink, lilac, baby blue, butter yellow) with cream and white.
- **Silhouette:** cropped or fluffy knits, pleats, soft volume.
- **Fabrics:** mohair-look knits, cotton, floral prints.
- **Key pieces:** cropped or oversized cardigan, pleated skirt, slip dress, ribbed tee.
- **Shoes:** retro sneakers in pastels, or Mary Janes.
- **Accessories:** small pastel bag, dainty gold, knitted hat, hair clips.
- **Borrow it from your closet:** your softest knit, in the palest colour you own, with no black anywhere.
- **App profile:** low contrast, knit, dresses, warm tones, gentle colour. Head-to-toe dark and hard contrast count against it.

## Minimalist (ミニマル)

- **Origins:** Scandinavian and capsule-wardrobe thinking: fewer, better pieces with clean lines, function and versatility.
- **Essence:** calm, precise, intentional.
- **Palette:** white, black, grey, beige and navy.
- **Silhouette:** clean and straight, with nothing fussy.
- **Fabrics:** quality basics: heavyweight cotton, wool, leather.
- **Key pieces:** perfect white tee, tailored trousers, black blazer, trench or statement coat.
- **Shoes:** clean leather sneakers, ankle boots, loafers.
- **Accessories:** a simple watch, leather tote, neutral scarf.
- **Borrow it from your closet:** two neutrals, no prints, everything pressed.
- **App profile:** neutrals, tonal, smart, slim bottom. Prints and colour mixing count strongly against it.

## Y2K (Y2K)

- **Origins:** the early 2000s pop wardrobe, revived by Gen Z.
- **Essence:** playful, shiny, nostalgic.
- **Palette:** baby pink, lilac, baby blue, silver and metallics.
- **Silhouette:** low-rise and flared below, cropped and fitted on top.
- **Fabrics:** stretch jersey, denim, velour, metallic and rhinestone details.
- **Key pieces:** baby tee (often with rhinestones or slogans), low-rise flared jeans, mini skirt, cargo pants, velour tracksuit.
- **Shoes:** chunky platform sneakers.
- **Accessories:** baguette bag, tinted rimless shades, beaded jewellery, butterfly clips.
- **Borrow it from your closet:** a small tight tee with flared jeans and one shiny accessory.
- **App profile:** colour mixing, print, denim, one pop, sporty. Smart pieces and head-to-toe dark count against it.

## Gorpcore (ゴープコア)

- **Origins:** named after "good ol' raisins and peanuts" trail mix: outdoor and hiking gear worn in the city. Technical shells are its status pieces, and trail runners are its biggest export.
- **Essence:** ready for a mountain you're not climbing. Practical and a little ironic.
- **Palette:** earthy greens, khakis and greys, with one bright shell (orange, yellow, cobalt).
- **Silhouette:** layered and roomy.
- **Fabrics:** fleece, ripstop nylon, technical shells.
- **Key pieces:** fleece pullover, technical shell, puffer, hiking pants.
- **Shoes:** trail runners (Salomon, HOKA, La Sportiva types).
- **Accessories:** belt bag, bucket hat or beanie, carabiners.
- **Borrow it from your closet:** a fleece under a rain jacket, with roomy trousers and your most technical trainers.
- **App profile:** sporty, layered, one pop, colour mixing. Smart pieces count against it.

## Old money (オールドマネー)

- **Origins:** "quiet luxury": the inherited-wealth wardrobe of country clubs and private schools. Quality without logos.
- **Essence:** understated, polished, expensive-looking without effort.
- **Palette:** cream, navy, camel, white and soft greys.
- **Silhouette:** tailored but relaxed. Nothing tight, nothing loud.
- **Fabrics:** cashmere, wool, silk, linen, suede.
- **Key pieces:** cable or cashmere knit, navy or beige blazer, pleated trousers, crisp shirt.
- **Shoes:** leather or suede loafers, ballet flats.
- **Accessories:** structured leather bag, a minimalist watch, pearls or fine gold.
- **Borrow it from your closet:** your best knit draped over a shirt, with tailored trousers in cream or navy.
- **App profile:** smart, knit, neutrals, warm tones, layered, low contrast. Sporty pieces count strongly against it.
- **Note:** most "old money" writing online is from brands selling the look, so treat the specifics as convention.

## Grunge (グランジ)

- **Origins:** the late-80s and early-90s Seattle music scene, an anti-fashion answer to polish.
- **Essence:** undone, comfortable, a bit defiant.
- **Palette:** plaid reds and greens, black, faded denim.
- **Silhouette:** oversized and layered: flannel over a tee, open.
- **Fabrics:** flannel, worn cotton, distressed denim, leather.
- **Key pieces:** flannel shirt (worn open or tied at the waist), band tee, ripped jeans.
- **Shoes:** combat boots, classically Dr. Martens 1460s, often unlaced.
- **Accessories:** beanie, wallet chain.
- **Borrow it from your closet:** an open overshirt over a graphic tee, with your most worn jeans and boots.
- **App profile:** denim, layered, print, relaxed top, a little dark. Smart pieces count against it.

---

## What the app does with it

1. **The warm-up.**
   - **The pairs:** two boards per pair. The first pairs are the most informative ones: largest posterior variance of the weight difference, times p(1 − p).
   - **No repeats:** no pair is asked twice, and no style appears more than twice in a round.
2. **The style mix.**
   - **The percentages:** the Bradley–Terry weights become percentages (a softmax), shown in Style DNA as "Styles you're drawn to".
   - **How sure:** each style is marked sure or not from its posterior.
3. **Your closet in the same terms.** Each style's profile is compared with the average outfit you actually wear, which gives "What your closet says".
4. **Room to grow.** The style you like most that your closet expresses least, with three signature pieces from the list above. It changes three things:
   - **The Stretch look** leans towards it.
   - **The planning agent** is told about it.
   - **The thrift agent** looks for those signature pieces second-hand, but only after the oni has checked what you already own.
5. **One model, two levels.** Each board pick is also a weak training row for the outfit taste model (this style's feature profile against the other's), so the warm-up teaches both at once.

## Sources

Retail and blog sources are useful for what people wear, less so for history. Where a claim rested on one weak source it was dropped or flagged above.

- Dark academia:
  - [The VOU: What is dark academia](https://thevou.com/fashion/dark-academia-style/)
  - [Ian Drummond Vintage: Dark academia](https://iandrummondvintage.com/blogs/fashion-history/dark-academia)
  - [thredUP: Dark academia key pieces](https://www.thredup.com/bg/p/dark-academia-fashion)
  - [Sew Guide: Dark academia fashion style](https://sewguide.com/dark-academia-fashion-style/)
- Streetwear:
  - [FashionBeans: Streetwear aesthetic](https://www.fashionbeans.com/article/streetwear-aesthetic)
  - [Denim Exchange: History of streetwear](https://denimexchangeusa.com/blogs/news/history-of-streetwear-fashion)
  - [Complex: Streetwear brands' first tees](https://www.complex.com/style/2015/02/streetwear-brands-share-first-t-shirt-designs)
- Cyberpunk / techwear:
  - [Printful: Cyberpunk fashion](https://www.printful.com/blog/cyberpunk-fashion)
  - [Cyber Techwear: Guide to cyberpunk clothing](https://cyber-techwear.com/blogs/techwear-blog/the-ultimate-guide-to-cyberpunk-clothing)
  - [Fuga Studios: Cyberpunk techwear aesthetic](https://fuga-studios.com/en/blogs/journal/cyberpunk-techwear-aesthetic)
- Gothic:
  - [RTÉ Brainstorm: Goth fashion history](https://www.rte.ie/brainstorm/2023/1025/1412925-goth-fashion-history)
  - [Hard'n'Heavy: Gothic style evolution](https://hardnheavy.style/blogs/blog/gothic-style-evolution-decades-of-elegance)
- Brutalist:
  - [Lekondo: Brutalism, explained](https://lekondo.substack.com/p/entry-003-what-is-the-brutalism-aesthetic)
  - [V Magazine: Moncler + Rick Owens, a brutalist summer](https://vmagazine.com/article/moncler-rick-owens-vision-for-a-brutalist-summer/)
  - [Apartstyle: Brands like Margiela](https://www.apartstyle.com/post/brands-like-margiela)
- Parisian chic:
  - [Woman & Home: French fashion staples](https://www.womanandhome.com/fashion/french-fashion-staples-for-a-parisian-chic-wardrobe/)
  - [Who What Wear: French-girl capsule](https://www.whowhatwear.com/uk/french-girl-capsule-wardrobe)
  - [The Gloss: Five staples French women love](https://thegloss.ie/french-women-style/)
- Soft:
  - [Refinery29: TikTok's soft girl aesthetic](https://www.refinery29.com/en-us/soft-girl-aesthetic-fall-fashion-trends)
  - [Screenshot: Soft girl wardrobe staples](https://screenshot-media.com/the-future/fashion/soft-girl-aesthetic-fashion-staples)
- Minimalist:
  - [Scandi.co.uk: Scandi-style capsule wardrobe](https://www.scandi.co.uk/capsule-wardrobe/)
  - [Woman & Home: Minimalist wardrobe essentials](https://www.womanandhome.com/fashion/10-minimalist-style-essentials-to-build-your-perfect-wardrobe)
  - [Marie Claire AU: Scandinavian style](https://www.marieclaire.com.au/fashion/scandinavian-style/)
- Y2K:
  - [ASOS: Y2K styling tips](https://www.asos.com/women/fashion-feed/2022_08_29-mon/y2k-fashion-styling-tips)
  - [VICE: Y2K fashion style guide](https://vice.com/en/article/qjv5nq/y2k-fashion-style-guide)
- Gorpcore:
  - [Field Mag: What is gorpcore](https://www.fieldmag.com/articles/what-is-gorpcore-guide)
  - [Opumo: What is gorpcore](https://www.opumo.com/magazine/what-is-gorpcore-men/)
  - [Farfetch: Hikercore and gorpcore](https://www.farfetch.com/ca/style-guide/trends-subcultures/hikercore-gorpcore-fashion/)
- Old money:
  - [Harper's Bazaar MY: Guide to the old money aesthetic](https://harpersbazaar.my/bazaar-man/the-ultimate-guide-to-old-money-aesthetic/)
  - [Real Men Real Style: Quiet luxury](https://www.realmenrealstyle.com/quiet-luxury-for-men/)
- Grunge:
  - [The VOU: grunge](https://thevou.com/?p=194285)
  - [Crossroads Trading: style blog](https://crossroadstrading.com/?p=33203)
