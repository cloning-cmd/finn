// Server-render every card of a saved Brief JSON with CardView (expanded) and report any that throw.
// Usage: npx tsx scripts/render-check.tsx <brief.json>
import { readFileSync } from "node:fs";
import { renderToString } from "react-dom/server";
import CardView from "../components/cards/CardView";
import type { Brief } from "../lib/types";

const brief = JSON.parse(readFileSync(process.argv[2], "utf-8")) as Brief;
let bad = 0;
for (const card of brief.cards) {
  try {
    const html = renderToString(<CardView card={card} compact={false} />);
    if (!html.includes(card.ticker)) throw new Error("ticker missing from output");
  } catch (e) {
    bad++;
    console.log("FAIL", card.id, card.type, card.ticker, String(e).slice(0, 160));
  }
}
console.log(`${brief.cards.length} cards rendered, ${bad} failed`);
process.exit(bad ? 1 : 0);
