# UI and motion craft from X (2026-10-17)

Sources: X through `opencli twitter` (search, then timelines after search hit HTTP 429), web through Jina Reader, GitHub through `gh`.

## A1. @Mnilax, "15 github repos that turn Opus 5.5 into a full design team" (Oct 14)
https://x.com/Mnilax/status/2110382356028686598

| # | Repo | What it gives Claude |
|---|---|---|
| 01 | frontend-design (Anthropic) https://github.com/anthropics/skills | UI that looks deliberate and has a point of view |
| 02 | stitch-skills (Google) https://github.com/google-labs-code/stitch-skills | makes screens, turns code back into designs, keeps one DESIGN.md |
| 03 | ui-ux-pro-max-skill https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | 192 palettes and 74 font pairings it can search (**already installed**) |
| 04 | impeccable https://github.com/pbakaus/impeccable | 24 commands (polish, critique, bolder) and 59 anti-AI-look rules (**already installed**) |
| 05 | agent-skills (Vercel) https://github.com/vercel-labs/agent-skills | checks UI against 100+ accessibility, performance and UX rules |
| 06 | excalidraw-mcp https://github.com/excalidraw/excalidraw-mcp | streams hand-drawn diagrams |
| 07 | tldraw https://github.com/tldraw/tldraw | agent starter kit that reads and edits a canvas |
| 08 | mcp-server-guide (Figma) https://github.com/figma/mcp-server-guide | builds frames, components and auto layout in Figma |
| 09 | Figma-Context-MCP https://github.com/GLips/Figma-Context-MCP | real Figma layout data instead of screenshots |
| 10 | cursor-talk-to-figma-mcp (Grab) https://github.com/grab/cursor-talk-to-figma-mcp | reads and edits Figma frames, text and styles |
| 11 | penpot https://github.com/penpot/penpot | open-source design tool with its own MCP |
| 12 | shadcn/ui https://github.com/shadcn-ui/ui | MCP to browse and install components by name |
| 13 | magic-mcp (21st.dev) https://github.com/21st-dev/magic-mcp | v0 inside Claude Code, 10k+ components |
| 14 | storybook https://github.com/storybookjs/storybook | MCP that hands the agent your existing components |
| 15 | onlook https://github.com/onlook-dev/onlook | visual editing of a Next.js app, synced to the code |

Related post: his Oct 11 "15 repos … motion design studio" (motion, gsap-skills, LottieFiles motion-design-skill): https://x.com/Mnilax/status/2109314840057565345

## A2. @himanshubuildss, 40 resources (posted Oct 10 US time / Oct 11 UTC). Top 15 for us
https://x.com/himanshubuildss/status/2109130327277142377

1. Scrolltide https://scrolltide.co: a prompt for each motion component
2. Refero Styles https://styles.refero.design: 2,000+ real product styles, with type
3. Mobbin https://mobbin.com: real mobile app flows (sign-in, onboarding)
4. DESIGNmd https://designmd.ai: design systems as markdown an agent can read
5. Component Gallery https://component.gallery: one element solved by many design systems
6. Minimal Gallery https://minimal.gallery: calm, high-end sites
7. Godly https://godly.website: sites built with real craft
8. landing.love https://landing.love: sites with the best animation
9. Land-book https://land-book.com: landing page references
10. Motion Primitives https://motion-primitives.com: advanced interactions
11. SmoothUI https://smoothui.dev: animated components built on Motion and GSAP
12. MicroKit https://microkit.co: micro-interactions for buttons and inputs
13. Kinetics https://kinetics.colorion.co: 150+ motion effects with prompts
14. 21st.dev https://21st.dev: component registry with MCP
15. Anime.js https://animejs.com: light animation engine for single-file mocks

## B. Craft moves to use today

1. **Press:** `:active{transform:scale(.97)}` with `transition:transform 160ms var(--ease-out)`. Emil Kowalski https://emilkowal.ski/ui/7-practical-animation-tips
2. **Easing tokens:** `--ease-out:cubic-bezier(.23,1,.32,1)`, `--ease-in-out:cubic-bezier(.77,0,.175,1)`, `--ease-drawer:cubic-bezier(.32,.72,0,1)`. Never use `ease-in` on UI. https://github.com/emilkowalski/skills (animate)
3. **Durations:** press 100–160ms, tooltip 125–200ms, dropdown 150–250ms, modal or sheet 200–500ms. Keep UI motion under 300ms. Same source.
4. **Springs (Apple values):** by default damping 1.0 (no bounce) with response 0.3–0.4s. Use 0.8 only after a flick. In Motion: `{type:'spring',bounce:0,duration:0.4}`. In pure CSS, generate `linear()` springs with https://linear-easing-generator.netlify.app. Emil's /apple-design skill https://x.com/emilkowalski/status/2075188252877672732 and Josh Comeau https://www.joshwcomeau.com/animation/linear-timing-function/
5. **Never start at scale(0):** enter from `scale(.93–.97)` plus `opacity:0`. Emil.
6. **Blur-in reveal:** go from `opacity:0; translateY(8px); filter:blur(4px)` to the resting state. Exits are subtler: a shorter move and a 4px blur. For icon swaps, scale .25→1 with blur 4px→0. Keep blur under 20px. Jakub Krehel https://interfaces.dev/cheat-sheet
7. **Stagger:** 30–80ms between items (50ms is a good default). Animate in small groups and never block input. Emil animate skill and Jakub.
8. **Mount without JS:** use `@starting-style{opacity:0;transform:translateY(8px)}`. Emil recipes.
9. **Number roll for the score:** set `font-variant-numeric:tabular-nums` (Jakub). For a digit-roll odometer, NumberFlow uses a 750ms spin, a 350ms ease-out opacity fade, and a `trend` setting that picks the roll direction (https://number-flow.barvian.me). Vanilla version: `@property --n{syntax:'<integer>';initial-value:0;inherits:false}` then `counter-reset:n var(--n)`, `::after{content:counter(n)}`, and `transition:--n 1.2s var(--ease-out)`.
10. **Shared element (course card → verdict):** wrap the update in `document.startViewTransition(()=>render())`. Put the same `view-transition-name:course-hero` on the card and the verdict header. Time it with `::view-transition-group(*){animation-duration:400ms;animation-timing-function:cubic-bezier(.32,.72,0,1)}`. Jhey Tompkins https://x.com/jh3yy/status/1630692737887420416 and Adam Argyle https://x.com/argyleink/status/1659619493151391744
11. **Scroll-driven reveals (learning view):** `animation:show linear both; animation-timeline:view(); animation-range:entry 0% cover 30%`. For a header that shrinks on scroll, use `animation-timeline:scroll()`. https://x.com/jh3yy/status/1689682832174587956 and https://x.com/jh3yy/status/1695199273980236275
12. **Arc carousel math (our rebuild):** stack every card at the apex. Give each one `transform-origin:50% calc(50% + R)` and `rotate:calc((var(--i) - var(--active)) * var(--step))`, with R about 3× the viewport width and step ≈ (card width + gap) / R in radians. That one rotation sets both the card's place on the arc and its tangent tilt. Dragging changes `--active` as a float; on release, snap it with a spring. Scrolltide's description plus Apple's projection below.
13. **Throw and land:** projected stop = `x + (v/1000)*0.998/(1-0.998)`, then snap to the nearest card. Edges get rubber-banding: `o*d*.55/(d+.55*|o|)`. Emil /apple-design.
14. **Spatial consistency:** things exit along the path they came in on. Popovers scale from their trigger (`transform-origin` set at the trigger). Emil.
15. **Apple type (live apple.com CSS):** body 17px / line-height 1.47 / weight 400 / tracking -0.022em. Headline 48px / 1.08 / 600 / -0.002em. Tile headline 56px / 1.07 / 600 / -0.005em. Content column 980px (692px on small screens). Font stack: SF Pro Display → system-ui. For very large display type, tighten to -0.02em at line-height 1.05. Source: https://www.apple.com/v/homepage/a/styles/main.built.css and Emil.
16. **Spacing and surfaces:** gaps between groups are at least 2× the gaps between items (8px vs 16px). Nested radii are concentric (outer = inner + padding). Use layered box-shadows instead of borders. Give images a 1px outline at 8% black. Jakub.
17. **Text wrap:** `text-wrap:balance` on headings and `pretty` on descriptions. Jakub.
18. **Glass chrome:** `background:rgba(255,255,255,.6); backdrop-filter:blur(20px) saturate(180%)`. Never stack glass on glass. Emil /apple-design.
19. **Guards:** hover styles go inside `@media (hover:hover)`. Under `prefers-reduced-motion`, swap slides and springs for a 200ms crossfade. Never write `transition:all`. Jakub and Emil.

Most useful single install: https://github.com/emilkowalski/skills (apple-design, animate, review-animations, mobile-native, animation-performance). For animation terms to use in prompts: https://animations.dev/vocabulary

## C. Scrolltide components that fit Day Trader AI
Scrolltide's own prompts are paid ("pro" tier). The public page data has `promptContent:""`, so we can't copy their prompt text. Below, each mechanic is quoted from their one-liners, followed by our own short prompt.

1. **Arc Carousel** (course picker). Cards ride a huge circle, the focused one upright at the apex, the rest tilted tangent to the curve, all from one rotation. *Prompt:* "Course picker: cards on an arc of radius 3× viewport, one shared rotation, drag with momentum, spring snap (bounce 0), focused card full opacity, the rest at .5."
2. **Layer Carousel** (course picker, calmer). A deck that steps back in size and blur on each side of the focused card. It autoplays with a progress line and springs between cards "with a hair of overshoot". *Prompt:* "Neighbours at scale .9/.8 and blur 2px/4px; arrows, drag and keys; spring bounce .1."
3. **Fan Carousel** (choosing a course). The focused card is lifted out of the spread, clear of the scale its neighbours share. *Prompt:* "Fan of courses; the selected card rises 24px and scales 1.08, past the step between neighbours."
4. **Focus Reveal** (the verdict word). Words stay blurred until a focus frame travels to each one and brings it sharp. *Prompt:* "Verdict 'YES'/'NO' starts at blur 12px; a measured focus box slides over it in 500ms ease-out and the word sharpens to 0."
5. **Morph Pill Card** (before → after). A pill grows into a full card, "one surface moving between two measured layouts". *Prompt:* "'Original course' pill morphs into the 'AI-improved' result card with a View Transition; contents fade in with a 50ms stagger."
6. **Showcase Card** (result details). A card opens into a summary whose parts sharpen out of a blur. *Prompt:* "Result card expands; stats, chips and text go from blur 4px to 0 with a 60ms stagger."
7. **Step Path** (learning view). Steps joined by one dashed line that draws itself as it scrolls in, each step fading up as the line arrives. *Prompt:* "Fix 1→N timeline; SVG stroke-dashoffset driven by `animation-timeline:view()`; each step's score counts up when the line reaches it."
8. **Step Accordion** (how it works). A numbered accordion with a picture that morphs into the next step, autoplaying and pausing while you read.

Other fits: Expanded Cards (the caption is laid out once at full width, so it never rewraps), Spotlight Carousel (re-crops instead of scaling), and the UI screens "Wallet Overview", "Finance Desk" and "Banking Home" at https://scrolltide.co/ui

## D. Five Apple-simple rules
1. **One hero per screen.** The verdict is the biggest thing; everything else is 17px.
2. **Space shows structure, not lines.** Use 2× gaps between groups and no dividers.
3. **Motion answers input.** Feedback starts on press, can be interrupted, and stays under 300ms.
4. **Springs with no bounce by default.** Overshoot only after a throw.
5. **Restraint over decoration.** System font, one accent colour, tabular numbers, glass only on chrome.

Not covered: X search was rate-limited (HTTP 429) after about 13 queries, so "dribbble fintech", "linear app design", "framer motion" and "mobile app UI" did not run.
