# Day Trader AI: 4 UI variations

Four concepts for the same 4 screens (sign in, onboarding, verdict per course, learning view), built from one shared spec and the same sample data, so they differ in design only. Each is one offline HTML file: open it in a browser.

| Variant | The idea | Signature move |
|---|---|---|
| [trial](trial/index.html) | Each course is a treatment tested against doing nothing ("just holding"). | A forest plot: dots left of the "just holding" line lost, right of it won. The same plot shows each fix walking right. |
| [stamp](stamp/index.html) | The answer is readable from across the room. | The whole screen turns the verdict colour and a rubber stamp ("NO", "BARELY") slams onto it. |
| [receipt](receipt/index.html) | Money talk: dollars, not percentages. | A receipt prints line by line; a rejected fix is printed as VOID. |
| [race](race/index.html) | The finishing order is the verdict. | Three swimmers race to their ending money; a rejected fix is DQ'd. |
| [**stamp-v2**](stamp-v2/index.html) | **The judge's winner, rebuilt Apple-simple** with motion from `notes/research/ui-craft.md`. | The stamp presses into focus and the numbers count up. The courses ride an arc carousel. |

Screens are hash routes: `#signin`, `#onboard-1` … `#onboard-3`, `#verdict-zip` / `#verdict-lpp` / `#verdict-cw`, `#proof-zip`, `#learn-zip`. Add `?still=1` to skip animations (for screenshots).

All numbers are sample data, labelled in the app. Course content is copyrighted, so the mocks show short rule quotes with citations only.

Fonts are macOS system faces (Avenir Next, DIN, Futura, Gill Sans, Menlo) with fallbacks; other platforms fall back to system sans.

Judging: stamp won (26/30), receipt was runner-up (22). See [notes/ui-judging.md](../../../notes/ui-judging.md). stamp-v2 applies the judge's 5 fixes.
