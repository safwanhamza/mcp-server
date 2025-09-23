# Scene and Presenter preset dictionaries for first-iteration dropdowns.
# These names match your UI labels; keys are machine-safe slugs.

SCENE_SETTINGS = [
    ("modern_minimalist_apartment", "Modern Minimalist Apartment"),
    ("cozy_home_office", "Cozy Home Office"),
    ("bright_modern_kitchen", "Bright Modern Kitchen"),
    ("trendy_urban_loft", "Trendy Urban Loft"),
    ("scandinavian_living_room", "Scandinavian Living Room"),
    ("beauty_room_setup", "Beauty Room Setup"),
    ("contemporary_bedroom", "Contemporary Bedroom"),
    ("home_gym_corner", "Home Gym Corner"),
    ("bohemian_living_space", "Bohemian Living Space"),
    ("modern_spa_bathroom", "Modern Spa Bathroom"),
    ("outdoor_patio", "Outdoor Patio"),
    ("minimalist_studio", "Minimalist Studio"),
    ("coffee_shop_corner", "Coffee Shop Corner"),
    ("plant_parent_paradise", "Plant Parent Paradise"),
    ("midcentury_modern_den", "Mid-Century Modern Den"),
    ("meditation_room", "Meditation Room"),
]

SCENE_DETAIL = {
    "modern_minimalist_apartment": {
        "env": "full modern minimalist apartment shown wall-to-wall: low-profile sofa, side table, floor lamp, framed art, open shelving with plants; clean lines, natural materials, subtle texture; realistic depth and parallax with foreground plant leaves and mid-ground furniture",
        "camera": "medium-wide framing capturing presenter head-to-knees; static tripod with slow cinematic push-in; slight parallax from foreground elements",
        "lighting": "controlled soft light, dimmed fill; gentle rim from floor lamp; conservative exposure, no bloom or glare, skin tones neutral and natural"
    },
    "cozy_home_office": {
        "env": "complete home office: desk with monitor, keyboard, stationery tray, bookshelf with staggered books and plants, cork board, soft rug; mug and notebook on desk; window with blinds partially closed",
        "camera": "medium-wide head-to-knees, locked off from slightly off-axis to show desk depth",
        "lighting": "warm key from shaded desk lamp, dim overhead practicals; subtle window fill; no hotspots on skin, highlight roll-off soft and realistic"
    },
    "bright_modern_kitchen": {
        "env": "modern kitchen shown from island to back wall: marble island with fruit bowl, induction hob, backsplash, upper cabinets, bar stools, small herb pots, stainless fixtures; reflections subdued and physically plausible",
        "camera": "medium-wide head-to-knees from island corner for depth; slight handheld sway kept minimal",
        "lighting": "tempered daylight softened by diffusion on windows; dim bounce fill; speculars controlled on counters; avoid overexposed whites"
    },
    "trendy_urban_loft": {
        "env": "industrial loft: exposed brick wall, steel beams, big factory windows, hanging Edison bulbs, vintage rug, tall plants, sideboard with decor; visible ceiling height for scale",
        "camera": "medium-wide dolly-in along brick wall giving depth; presenter centered with architectural lines leading",
        "lighting": "soft daylight key angled from windows with dim tungsten practical accents; conservative bloom, no flares; shadow detail preserved"
    },
    "scandinavian_living_room": {
        "env": "Scandi living room: light wood floors, linen sofa, nesting tables, leafy plants, woven baskets, textured throw, sheer curtains, neutral palette with subtle contrast",
        "camera": "medium-wide head-to-knees, eye-level tripod; a few foreground branches for depth layering",
        "lighting": "bright but controlled soft daylight; negative fill on off-camera side for gentle shape; no clipped highlights"
    },
    "beauty_room_setup": {
        "env": "creator vanity area: backlit mirror with dimmable bulbs, acrylic organizers, floating shelves with skincare, stool, backdrop stand in corner; tidy yet lived-in aesthetic",
        "camera": "medium-wide head-to-knees; lens height slightly above chest for flattering perspective",
        "lighting": "broad soft key with diffused wrap, dim background practicals; sheen minimized on skin; no beauty-light glow or excessive smoothing"
    },
    "contemporary_bedroom": {
        "env": "full bedroom: upholstered headboard, layered bedding, pendant lights, framed artwork, plant on dresser, textured rug; doorway and window visible for depth cues",
        "camera": "medium-wide, head-to-knees from foot of bed; gentle push-in or static",
        "lighting": "soft morning-style key diffused through curtains; dim fill; practicals at low intensity for ambiance; no blown whites on bedding"
    },
    "home_gym_corner": {
        "env": "functional gym nook: rubber mat, dumbbell rack, kettlebells, foam roller, resistance bands on hooks, mirror panel, potted plant; breathable space around equipment",
        "camera": "medium-wide head-to-knees, slight off-axis to reflect mirror depth without showing camera",
        "lighting": "controlled daylight plus low-intensity overhead; skin speculars tamed; avoid harsh rim; balanced contrast"
    },
    "bohemian_living_space": {
        "env": "boho lounge: patterned rugs, macrame wall hangings, floor cushions, rattan chair, layered plants, warm wood accents, candles on tray; rich textures without clutter",
        "camera": "medium-wide, head-to-knees with shallow dolly to reveal textures; foreground woven basket for parallax",
        "lighting": "warm key moderated to mid-level; string lights dim; candle highlights soft and contained; no glow effect"
    },
    "modern_spa_bathroom": {
        "env": "spa bathroom: stone vanity, matte fixtures, frosted glass, folded towels, eucalyptus sprig, subtle steam effect near shower, pebble mat; subdued reflections",
        "camera": "medium-wide head-to-knees from vanity angle; static with micro push",
        "lighting": "cool soft key with low fill; reflections controlled; no specular glare on tiles; skin tones neutral without shine"
    },
    "outdoor_patio": {
        "env": "patio scene: wooden deck, planters with greenery, outdoor sofa with cushions, side table, lanterns, distant garden fence for scale; subtle breeze motion in leaves",
        "camera": "medium-wide head-to-knees, static; slight foreground foliage crossing for depth",
        "lighting": "golden-hour look but dimmed; soft directional key with negative fill; avoid orange cast and blown highlights"
    },
    "minimalist_studio": {
        "env": "seamless backdrop studio with stool, C-stand and flag visible subtly to keep realism, small side table; clean floor-to-backdrop transition",
        "camera": "medium-wide head-to-knees; locked tripod; lens compression modest",
        "lighting": "soft key and low fill with controlled contrast; backdrop lit separately at lower stop; no edge bloom"
    },
    "coffee_shop_corner": {
        "env": "cafe corner: wooden table, ceramic mug with saucer, pastry plate, window with street blur, bookshelf with plants, barista station hinted in background bokeh",
        "camera": "medium-wide head-to-knees from window angle; static; slight external motion in background for life",
        "lighting": "soft window key with dim fill; practical pendants at low output; reflections controlled on mug"
    },
    "plant_parent_paradise": {
        "env": "lush apartment room: layered plants (monstera, pothos, snake plant), ladder shelf, watering can, woven baskets, textured throw; varied leaf sizes for depth",
        "camera": "medium-wide head-to-knees; occluding leaves in foreground corners for parallax",
        "lighting": "bright diffused daylight but reduced overall exposure; cool fill to neutralize green spill; no glowy highlights on skin"
    },
    "midcentury_modern_den": {
        "env": "mid-century den: walnut paneling, low credenza, record player, tapered-leg chair, geometric art, floor lamp with drum shade; warm retro accents",
        "camera": "medium-wide, slow dolly parallel to paneling lines; head-to-knees framing",
        "lighting": "soft warm key with subtle rim from floor lamp; highlight roll-off gentle; no excessive warmth or bloom"
    },
    "meditation_room": {
        "env": "serene studio: tatami mat, low bench, shoji screen, candles, small altar shelf, woven wall art; uncluttered negative space",
        "camera": "medium-wide, static head-to-knees; centered composition with symmetrical balance",
        "lighting": "dim warm ambience, low-intensity key; candle practicals at minimal output; skin matte and even"
    },
}


PRESENTER_STYLES = [
    ("relatable_girl_next_door", "Relatable Girl Next Door"),
    ("professional_trustworthy", "Professional & Trustworthy"),
    ("trendy_genz_creator", "Trendy Gen-Z Creator"),
    ("sophisticated_authority", "Sophisticated Authority"),
    ("athletic_motivator", "Athletic Motivator"),
    ("bohemian_artist", "Bohemian Artist"),
    ("corporate_professional", "Corporate Professional"),
    ("relatable_young_mom", "Relatable Young Mom"),
    ("beauty_enthusiast", "Beauty Enthusiast"),
    ("wellness_coach", "Wellness Coach"),
    ("fashion_forward", "Fashion Forward"),
    ("tech_savvy_millennial", "Tech-Savvy Millennial"),
    ("grandmillennial_style", "Grandmillennial Style"),
    ("edgy_alternative", "Edgy Alternative"),
    ("natural_hair_queen", "Natural Hair Queen"),
    ("minimalist_aesthetic", "Minimalist Aesthetic"),
    ("relaxed_skater_vibes", "Relaxed Skater Vibes")
]

PRESENTER_DETAIL = {
    "relatable_girl_next_door": {
        "persona": "friendly, approachable female host in light yellow outfit, natural black hair, understated makeup",
        "voice": "warm, conversational, mid tempo",
        "delivery": "smiles, light hand gestures, relaxed posture",
        "camera": "framed head-to-knees, standing or seated naturally; eye-level",
        "skin": "clear, wrinkle-free, natural matte tone; no artificial glow or excessive smoothing"
    },
    "professional_trustworthy": {
        "persona": "confident female presenter in business-casual light blue attire, neat black hair, minimal jewelry",
        "voice": "clear, credible, deliberate pace",
        "delivery": "minimal gestures, direct eye contact, composed stance",
        "camera": "head-to-knees, straight-on or slight 3/4 angle",
        "skin": "matte, balanced highlights; natural texture preserved, no shine"
    },
    "trendy_genz_creator": {
        "persona": "high-energy female creator in modern streetwear, styled black natural hair, contemporary accessories",
        "voice": "upbeat, quick cadence",
        "delivery": "expressive but controlled gestures",
        "camera": "head-to-knees with subtle motion framing to match energy",
        "skin": "natural matte; avoid glossy speculars and glow filters"
    },
    "sophisticated_authority": {
        "persona": "polished female expert in tailored outfit, refined styling (no red hair)",
        "voice": "controlled, authoritative",
        "delivery": "measured gestures, poised presence",
        "camera": "head-to-knees at eye level; minimal movement",
        "skin": "even tone, soft roll-off on highlights; no plastic sheen"
    },
    "athletic_motivator": {
        "persona": "female fitness coach in athleisure, hair tied back (no red), energetic but approachable",
        "voice": "energetic, motivational",
        "delivery": "active gestures with stable core posture",
        "camera": "head-to-knees, slight off-axis to show environment depth",
        "skin": "matte finish; sweat sheen restrained and realistic"
    },
    "bohemian_artist": {
        "persona": "female creative with boho-chic outfit, natural hair tone (no red), artisanal accessories",
        "voice": "soft but confident",
        "delivery": "gentle expressive gestures",
        "camera": "head-to-knees centered or rule-of-thirds composition",
        "skin": "soft, matte, natural; avoid glow/bloom"
    },
    "corporate_professional": {
        "persona": "female corporate professional, blazer, tidy hairstyle (no red), subtle makeup",
        "voice": "confident and clear",
        "delivery": "subtle, efficient gestures",
        "camera": "head-to-knees, slightly elevated lens for authority",
        "skin": "matte natural complexion; no glossy hotspots"
    },
    "relatable_young_mom": {
        "persona": "friendly female parent in comfortable casuals, practical hairstyle (no red), warm demeanor",
        "voice": "warm and supportive",
        "delivery": "gentle, welcoming gestures",
        "camera": "head-to-knees at eye level, seated or standing",
        "skin": "clear and natural; no artificial brightness"
    },
    "beauty_enthusiast": {
        "persona": "female beauty creator with styled hair (no red) and polished makeup that remains natural on camera",
        "voice": "enthusiastic, friendly",
        "delivery": "demonstrative with products",
        "camera": "head-to-knees with slight push when showcasing items",
        "skin": "smooth matte finish; controlled highlights; no glow filter"
    },
    "wellness_coach": {
        "persona": "female wellness coach with calm presence, natural hair tone (no red), soft neutral attire",
        "voice": "soothing yet clear",
        "delivery": "grounded, slow gestures",
        "camera": "head-to-knees, centered and static",
        "skin": "even, matte; avoid brightening effects"
    },
    "fashion_forward": {
        "persona": "stylish female creator, curated outfit, natural hair tones (no red), editorial but approachable",
        "voice": "confident, light trendy slang",
        "delivery": "expressive poses with controlled movement",
        "camera": "head-to-knees with subtle dolly for look reveals",
        "skin": "matte with soft diffused key; no plasticity"
    },
    "tech_savvy_millennial": {
        "persona": "female presenter in smart-casual with gadgets as props, natural hair (no red)",
        "voice": "clear, upbeat",
        "delivery": "crisp gestures, purposeful beats",
        "camera": "head-to-knees slightly off-center to include tech props",
        "skin": "neutral matte tone; no specular hotspots"
    },
    "grandmillennial_style": {
        "persona": "female with classic-meets-modern aesthetic, natural hair color (no red), tasteful accessories",
        "voice": "pleasant and composed",
        "delivery": "poised gestures",
        "camera": "head-to-knees with symmetrical framing when possible",
        "skin": "soft matte; highlight control prioritized"
    },
    "edgy_alternative": {
        "persona": "female alt style with bold accessories, natural hair tones (no red), confident attitude",
        "voice": "confident, cool",
        "delivery": "punchy, minimal but assertive gestures",
        "camera": "head-to-knees with slight low-angle for attitude",
        "skin": "matte; avoid glossy sheen and glow"
    },
    "natural_hair_queen": {
        "persona": "female with natural textured hair (non-red), chic minimal outfit; hair and product emphasis",
        "voice": "warm and confident",
        "delivery": "intentional gestures highlighting hair",
        "camera": "head-to-knees with mild arc to follow hair movement",
        "skin": "matte and even; no excessive smoothing"
    },
    "minimalist_aesthetic": {
        "persona": "female minimalist outfit with clean lines, natural hair (no red), understated styling",
        "voice": "calm, concise",
        "delivery": "subtle gestures, steady presence",
        "camera": "head-to-knees, static symmetrical frame",
        "skin": "neutral matte; no glow or bloom"
    },
    "relaxed_skater_vibes": {
        "persona": "female with relaxed skater energy, natural hair tone (no red), casual layers",
        "voice": "laid back, friendly",
        "delivery": "loose, unforced gestures",
        "camera": "head-to-knees, slight lateral move for dynamic feel",
        "skin": "matte natural texture; avoid shiny highlights"
    }
}
