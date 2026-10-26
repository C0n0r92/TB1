# Compliance: Can a user in Ireland trade on Polymarket?  (Track 4)
Fetched: 2026-10-23 (UTC). All sources public, read-only. No account, wallet, or sign-in was used.

## VERDICT: RESTRICTED — no new positions from Ireland (treat as BLOCKED for our purposes)
Every official Polymarket source we checked lists Ireland (IE) as restricted. They disagree only on whether an *existing* position can still be closed. No source allows *opening* a position from Ireland. Our lab stays paper-only and research-only.

## Key quotes
1. **Developer docs, Geographic Restrictions**: https://docs.polymarket.com/developers/CLOB/geoblock (same text at https://docs.polymarket.com/api-reference/geoblock)
   - "Close-only means users can close existing positions but cannot open new ones."
   - Under "Regulatory-Restricted Jurisdictions (Close-Only on Frontend)": "Close-only on the Polymarket frontend; the API itself is not restricted." Ireland (IE) is listed in this table, along with Japan, Malta (sports only), the Netherlands and South Korea.
   - Our reading: the line "API itself is not restricted" is **not** permission to trade from Ireland through the API. The Terms bar anyone in a restricted jurisdiction (see quote 3), and Irish law requires a GRAI licence (see quote 4).
2. **Help Center, Geographic Restrictions** (dated Aug 14, 2026): https://help.polymarket.com/en/articles/13364163-geographic-restrictions
   - "The following 39 countries are completely restricted from accessing Polymarket: … IE | Ireland …"
   - "Polymarket strictly prohibits the use of VPNs or similar tools to bypass geographic restrictions. Such actions are considered violations of the platform's Terms of Service (Section 2.1.4)."
3. **polymarket.com trade-attestation text**, embedded in the polymarket.com/tos page bundle. The full Terms body loads client-side and did not render in a read-only fetch, so we could not quote §2.1.4 word for word.
   - "By trading, you agree to the [Terms] and attest that you are not (i) a U.S. person; (ii) located in the United States, France or other restricted jurisdiction; and (iii) using a VPN or other measures to circumvent or attempt to circumvent restrictions. Polymarket reserves the right to put your wallet in close-only mode if you do not comply with these Terms."
4. **Context: Irish Examiner, 21 Jul 2026**: https://www.irishexaminer.com/news/courtandcrime/arid-41883400.html
   - Polymarket geoblocked Ireland after the Gambling Regulatory Authority of Ireland (GRAI) intervened. From 1 Jul 2026, remote betting operators need a GRAI licence. GRAI: "accounts identified as located in Ireland are currently restricted from depositing funds or opening new positions."

## Public geoblock endpoint
`GET https://polymarket.com/api/geoblock` is documented and returns `{blocked, ip, country, region}`. From this research box it returned `{"blocked":true,"country":"US","region":"VA"}`. The box is in the US, which is also restricted, and that does not affect read-only market data.

## International vs US exchange
- **polymarket.com (international)**: "not regulated by the CFTC and operates independently". The US, UK, France, Germany and others are restricted. Ireland is restricted (see above).
- **Polymarket US**: "operated by QCX LLC d/b/a Polymarket US, a CFTC-regulated Designated Contract Market" (polymarket.com footer). It is for US users. It does **not** open access for users in Ireland. The banner on polymarket.com reads: "Trading is blocked in the United States on polymarket.com. Switch to polymarket.us".

## VPN
Using a VPN or any other way around the geoblock is **never** an option. It breaks the ToS (§2.1.4 per the Help Center) and would likely breach Irish gambling regulation. This lab uses only public read-only data and paper trades.

## Open item
The full ToS text at polymarket.com/tos renders client-side. A human should read it in a normal browser to quote §2.1.4 and the restricted-persons clause verbatim. Do not sign in to do this.
