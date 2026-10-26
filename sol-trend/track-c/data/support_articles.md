---
title: Where are my private keys?
summary: Embedded wallet keys can't be exported, but funds remain fully accessible.
contact: true
---

If you signed in with email or Google, World creates an embedded wallet for you. Its
private key stays sealed inside it, invisible to you, World, and even support.

While you can't access the private key, you can [withdraw](/support/how-do-i-withdraw) funds at
any time.

If you connected an external wallet instead, the keys belong to that wallet and you manage them there.


=====

---
title: What can I ask my AI agent to do?
summary: Look things up, work through the numbers, and place orders when you tell it to.
---

Ask your AI agent about markets in plain language, and tell it when you want an order placed.

If you have not connected one yet, start with
[how do I trade with my AI agent?](/support/trade-with-ai-agent)

**The prompts below are invented examples of how a question can be phrased. They are not trading
advice, World does not recommend them, and nothing here implies that any of them will be
profitable.**

## Checking whether a market is close to even

:::prompt
Pull the live orderbook and the last ten minutes of price history for the current Bitcoin hourly
market. Is it sitting near 50/50, or is there real conviction one way? Tell me if it is moving
fast close to the deadline.
:::

A price near 50¢ can mean two things. The market may genuinely not know, or it may be swinging hard
and passing through the middle. Those look identical on the price alone.

## Reading the shape of a market

:::prompt
Read every price bucket in the Nasdaq 100 year-end market and describe the implied distribution.
Where is the mode, is it skewed up or down, and where do the tails thin out?
:::

A market with many price buckets is a forecast rather than a single number. The buckets together
show what the market expects and how confident it is.

:::note
Your agent can be wrong, and its analysis is its own rather than advice from World. Check
anything before you act on it. You are responsible for any order it places for you.
:::


=====

---
title: How do I trade with my AI agent?
summary: Connect World to your AI agent using PayBox, then ask it in plain language.
---

**PayBox** gives your AI agent access to World markets, so the smartest models can trade alongside
you.

Connect one, then talk to it about markets in plain language. It can look things up for you, work
through the numbers, and place orders when you tell it to, without ever handing over your keys.

## How to connect

Choose **Trade with** at the top of any page. Pick your agent and the window shows the exact
steps for it, along with the connector link you need to paste.

![The Trade with button, at the top right of any page.](/assets/support/trade-with-button.webp)

It takes a couple of minutes and you only do it once.

## What it can and cannot do

Your agent signs orders through your wallet, exactly as you do. **It cannot move your funds
anywhere else**, and it cannot spend beyond the limits you set when you connect.

Once it is connected, see [what you can ask it](/support/how-to-use-paybox).


=====

---
title: Which AI agents can I use?
summary: Claude, ChatGPT and Grok.
---

Three: **Claude**, **ChatGPT** and **Grok**.

Setup differs a little between them. The **Trade with** button at the top of any page has the exact
steps for each. Pick your agent there and follow the walkthrough.


=====

---
title: How do I deposit funds?
summary: Add funds with your wallet, a card, or an exchange.
contact: true
---

World accepts deposits in many tokens, across many networks. They all arrive as the stablecoin, CASH, the currency you place predictions in and get paid in.

Choose **Deposit** from your portfolio to see the current list.

:::phone
![The Deposit window, with its three ways to add funds.](/assets/support/deposit-methods.webp)
:::

- **Add Money**: buy with a card, Apple Pay or PayPal.
- **Connect Exchange**: send from an exchange account you already have.
- **Transfer Manually**: send crypto from another wallet.

## Sending crypto manually

Pick the currency and network you are sending from, then send to the address or QR code World
shows you.

**The address shown will be different from your World address**, even when sending funds on
Solana. This allows us to swap incoming tokens to CASH, the currency used when placing predictions.

:::phone
![Choosing a currency and network, and the address to send to.](/assets/support/cross-chain-deposit.webp)
:::

:::note
Send only the currency and network World shows on screen. If you send a different one, World cannot
recover your funds.
:::

## Tracking a deposit

Deposits arrive in a few seconds to a couple of minutes, depending on the network you sent from.
Choose **Track Deposits** at the bottom of the Deposit window to see everything you have sent,
where it came from, and whether it has arrived.

:::phone
![The Track Deposits window, listing recent deposits and their status.](/assets/support/track-deposits.webp)
:::


=====

---
title: What am I charged?
summary: A small fee when you buy, sell, deposit or withdraw. Nothing when a market resolves in your favor.
contact: true
---

It depends on what you are doing.

## When you buy

A small network fee comes out of the token you paid with.

Your first buy in a market costs a little more. The extra is a refundable deposit (rent), and it
comes back when the market ends. Buy into the same market again and there is no second deposit to
pay.

If you sell before the market ends, the deposit stays held until then.

## When you sell

A small network fee comes out of the token you receive, the same as on a buy.

## When you deposit

A small fee comes out of the amount you send, so slightly less arrives than you
[deposited](/support/how-do-i-deposit).

The wallet or exchange you send from may charge its own fee on top. If far less arrived than you
expected, the difference was taken before your funds reached World.

## When you withdraw

The [Withdraw](/support/how-do-i-withdraw) window shows the fee before you confirm.

## When you get paid

Nothing. You [get paid](/support/how-do-i-get-paid) in full.


=====

---
title: How do I sign in to World?
summary: With an email, a Google account, or a wallet you already have.
contact: true
---

:::desktop
Choose **Log In**, at the top right.
:::

:::mobile
Choose **Log In**, at the bottom of the screen.
:::

:::phone
![The Log In button.](/assets/support/login-button.webp)
:::

Email and Google create a wallet for you as you sign in. If you already have a Solana wallet, you
can connect that instead.

:::phone
![The log in window, with all three ways in.](/assets/support/login-window.webp)
:::

## With an email

Enter your email. World sends you a code, and typing it in signs you in.

## With Google

Choose **Continue with Google**, then pick your account.

## With a wallet you already have

Choose **Continue with Wallet**, then pick yours from the list. Phantom, Solflare, Coinbase Wallet
and Ledger are all there, along with WalletConnect for anything else.

## Once you are in

A new wallet starts empty, so the next step is to [add funds](/support/how-do-i-deposit).

:::phone
![Your portfolio, ready to use.](/assets/support/login-done.webp)
:::


=====

---
title: What is a prediction market?
summary: A market on the outcome of a real-world event, priced between $0 and $1.
---

In a prediction market you trade on the outcome of a real-world event. Each market asks one
yes-or-no question and pays out based on what actually happens. For example:

- Will Arsenal win the Premier League?
- Will Bitcoin be higher by the end of the day?

You take a YES or NO position at a price between $0 and $1, and that price reflects how likely the
market thinks the outcome is.

## The price is the probability

A YES at 62¢ means the market thinks there is about a 62% chance it happens. The price is the
market's estimate of the odds. This is called the **implied probability**.

YES and NO always add up to about $1. If YES is 62¢, NO is about 38¢. When the price moves, the
market has changed its mind about how likely the outcome is.

World shows both the price and the percentage next to each outcome, so you can read it either way.

Questions like that sit together on one card, which shows how many outcomes it covers.

:::phone
![Markets grouped by question, each card showing how many outcomes it covers.](/assets/support/what-is-a-prediction-market.webp)
:::


=====

---
title: What if a market can't resolve to a clear YES or NO?
summary: In rare cases, YES and NO each pay a portion of $1.
---

This happens when the underlying event can't produce a clear YES or NO, typically because it's
canceled, voided, or postponed indefinitely before it can settle. When that happens, YES and NO
each redeem for a share of $1 proportional to the result, rather than one side taking it all.

For example, a market that resolves at 60% pays YES about $0.60 per token and NO about $0.40. Your
downside is still capped at what you paid, and redemption is automatic by default.


=====

---
title: What is a TWAP?
summary: An asset's average price over a window, used to settle some Up/Down markets.
---

A Time-Weighted Average Price (TWAP) is an asset's average price over a time window. Some crypto
markets settle using a Chainlink TWAP feed.

Crypto prices can change in a millisecond, so the price at the exact moment a market closes is only
a snapshot. Rather than let that one moment decide the outcome, a TWAP reflects the price across
the whole window, a fuller picture of where the asset traded over that period.

## Why a closing price here can differ from another site

Cryptocurrencies trade on many independent exchanges at once, and prices vary slightly by venue. A
chart on another site shows the latest trade there; World settles on a Chainlink TWAP feed, so it's
possible the two won't match exactly.


=====

---
title: What is an outcome token?
summary: What you hold when you take a position. The winning side pays $1.
---

The token you hold when you take a position. Every market has two: a YES token and a NO token.
When the market resolves, the correct side pays out $1 per token and the other pays
nothing. In rare cases a market resolves to a partial, or scalar, outcome instead.

You buy them at a price between $0 and $1 that reflects the market's view of the outcome: a YES at
$0.62 means the market sees about a 62% chance it resolves YES, and a market's YES and NO prices
add up to roughly $1. They are standard Solana (SPL) tokens held in your own wallet, so you can
hold, sell, or transfer them.


=====

---
title: Can other people see my positions and activity?
summary: Yes. If you are ranked, anyone can open your profile and see your positions and activity.
---

Yes. Anyone can open the profile of a ranked trader. It shows:

- **Positions**: the markets they hold now, with the side, size, value and P&L.
- **Activity**: what they bought, sold and settled, newest first.

:::phone
![A trader's profile, with the Positions and Activity tabs below their stats.](/assets/support/trader-profile.webp)
Sample data. Names and figures are examples.
:::

Your positions and activity are the same information anyone can read from your wallet address on
Solana. The leaderboard shows it in one place, under your username or your X handle if you
connected one. It does not show your email.


=====

---
title: How do I change my name or show my X handle?
summary: Edit your username from the account menu, or connect X from your profile.
---

## Changing your username

Open the account menu at the top right and choose the pencil next to your name. Type a new name and save.

Names are 3 to 20 characters, using letters, numbers and underscores, and must start and end with
a letter or number. A name someone else has taken is rejected.

## Showing your X handle

1. Open the account menu at the top right and choose **Your Profile**.

   :::desktop
   Choose the » button beside the **30 days** menu on your profile, on the right, to collapse the
   leaderboard. **Edit** then appears next to your name.
   :::

   :::mobile
   Choose the pencil at the top of your profile.
   :::

2. Next to **X Account**, choose **Connect** and follow the steps.

   :::phone
   ![The Edit Profile window, with X Account and its Connect button.](/assets/support/edit-profile.webp)
   :::

Once X is connected, the leaderboard shows your X handle instead of your username, and your profile
links to your X account. Choose **Disconnect** in the same place to go back to your username.


=====

---
title: How is my rank decided?
summary: By realized profit and loss in the window you select. Volume breaks ties.
---

Traders are ranked by realized profit and loss (P&L) over the window you select: 24 hours, 7 days
or 30 days. Volume breaks ties.

:::phone
![The leaderboard, with the time filter beside the title and each trader's volume, P&L and markets.](/assets/support/leaderboard-table.webp)
Sample data. Names and figures are examples.
:::

## Profit and loss

A position counts toward your P&L when it closes, which is when you sell it or the market settles.
A buy has no P&L until then, and a position you still hold does not count.

The profit or loss lands in the window when the position closes, not the window when you bought.
It is measured against the average price you paid for that position.

## Volume

Volume is the total of your buys and sells in the window. A market settling is not a trade, so it
does not count, which is why your [volume can be blank](/support/why-is-my-volume-blank).

## When you have no rank

If you made no trades and no positions settled in the window, you have no rank and it shows **--**.
Rankings update on their own and take some time to reflect new activity.


=====

---
title: Can I use the leaderboard with an external wallet?
summary: Only embedded wallets are ranked.
---

No. Only embedded wallets are ranked. Trades made with an external wallet do not count, and you will
not appear on the board.

An embedded wallet is the one World creates when you sign in with email or Google. If you chose
**Continue with Wallet** when you [signed in](/support/how-do-i-sign-in), you have an external
wallet.


=====

---
title: Why is my volume blank?
summary: Volume counts buys and sells. A position settling in the window is not a trade.
---

Volume counts only your buys and sells in the window you selected. If the only thing that happened
in the window was a position settling, your volume is blank, but your [P&L](/support/how-is-my-rank-decided) reflects the position that
settled.

For example, with **24 hours** selected: you bought into a market two days ago, and it settled this
morning. You made no trades in the last 24 hours, so your volume is blank. The profit or loss from
the settlement shows in your P&L.

A buy inside the window always counts as volume, even if you hold it until it settles. The
settlement itself never does.


=====

---
title: How do I get paid when a market ends?
summary: Automatically. Winnings arrive in your wallet with nothing for you to do.
contact: true
---

When a market ends, your winning position is (almost always) paid automatically and funds arrive
in your wallet. You do not need to claim it.

## If you see a Redeem button

Some positions need you to finish the payout yourself. When that happens, **Redeem** appears at the
top of the page with the amount waiting for you.

![The Redeem button at the top of the page, beside your portfolio balance.](/assets/support/redeem-top-nav.webp)

The same positions are listed under **Redeem** in your portfolio.

Choosing either one opens the markets waiting to be paid. Each has its own **Redeem** button,
so if you are holding more than one, pay them out one at a time.

![The Redeem window, listing each market with its own Redeem button.](/assets/support/redeem-action.webp)


=====

---
title: My market ended, why haven't I been paid yet?
summary: Payouts are automatic and usually quick. A few things can hold one up.
contact: true
---

Payouts happen on their own, and most arrive within a minute of a market ending. If yours has not,
one of these is usually why.

## The market is still settling

Crypto markets settle the moment they close. Markets on real-world events
[wait a short while first](/support/when-does-a-market-settle), in case the announced result is
corrected.

## The event was postponed

If a match is called off, the market does not end with it. It stays open until the event actually
happens, or until it is clear that it will not.

Your position is still yours in the meantime, and you can sell it if someone is buying.

## The payout could not be made automatically

Very occasionally a position cannot be paid on its own. When that happens it shows in your
Portfolio with a [Redeem option](/support/how-do-i-get-paid) beside it, and choosing it pays you
there and then.


=====

---
title: When does a market settle?
summary: Crypto markets settle as soon as they close. Event markets take a little longer.
contact: true
---

It depends on the market.

## Crypto markets

Crypto markets settle as soon as they close. Payments usually arrive within 1 minute.

## Markets on real-world events

A market based on a sports match or an election takes longer, as we allow for a brief challenge
window to ensure the initial result is accurate.

1. First a provisional result is posted.
2. Then there is a short waiting period, allowing for the initial result to be disputed.
3. Finally the market settles.

## How do I know when my market settles?

Each market has a "Description" section under its graph covering how it settles.

:::phone
![The Description section under a market's graph.](/assets/support/market-description.webp)
:::


=====

---
title: Who decides the outcome of a market?
summary: An independent oracle, not World. Every step is recorded onchain.
contact: true
---

The result comes from an independent service called an **oracle**, which reports what
happened and publishes it onchain on Solana. The market settles from that report.

## How the result gets there

For crypto markets, the oracle reports a price. If the market asks whether Bitcoin ends higher than
it started, the oracle supplies both prices and the market settles on them. No judgment is
involved.

For real-world events, the result is posted, then held briefly in case it is corrected, then made
final. [When does a market settle?](/support/when-does-a-market-settle)


=====

---
title: How do I earn rewards from referrals?
summary: You earn a share of the fees your referred traders pay, once you and they have each connected X.
contact: true
---

You earn a share of the fees your referred traders pay on their trades. You earn from a trader only
when you and they have each connected X.

It is paid automatically, so there is nothing to claim. The Rewards page shows your total, and the
Referrals list shows how much each trader has earned you.

## Connecting X

1. Open the account menu at the top right and choose **Your Profile**.

   :::desktop
   Choose the » button beside the **30 days** menu on your profile, on the right, to collapse the
   leaderboard. **Edit** then appears next to your name.
   :::

   :::mobile
   Choose the pencil at the top of your profile.
   :::

2. Next to **X Account**, choose **Connect** and follow the steps.

   :::phone
   ![The Edit Profile window, with X Account and its Connect button.](/assets/support/edit-profile.webp)
   :::

Your referred trader does the same on their own account.


=====

---
title: Why isn't my friend showing up in my referrals?
summary: A friend counts once they confirm your invite, and only for the first person who referred them.
contact: true
---

A friend appears in your referrals once they confirm your invite. If a friend is missing, one of these
reasons is usually why.

## They did not confirm the invite

When your friend signs in through your link, World asks them to **Confirm invite** with a wallet
signature. If they close the window or choose **Maybe later**, the referral is not recorded.

Ask them to open your link again within an hour of creating their account, which brings the prompt
back.

## They signed up without your link

If your friend signed up without opening your link, no referral was recorded. Within an hour
of creating their account, they can open your link and choose **Confirm invite** to add the
referral. After that hour, the referral won't be recorded.

## Someone else referred them first

Each person can be referred once, by the first invite they confirm. If your friend confirmed
someone else's invite earlier, that person keeps the credit, even if your friend confirms yours
later.


=====

---
title: Can I get liquidated?
summary: No. There is no leverage and no margin, so there is nothing to liquidate.
---

Each outcome token costs between $0 and $1, and you pay its full price up front, so every position
is fully collateralized. Your downside is capped at what you paid.


=====

---
title: What is the most I can lose?
summary: The price you paid, and no more. There are no margin calls.
---

You pay for a position in full up front, and it can never be worth
less than zero, so if your side loses, that cost is your whole loss. There are no margin calls and
no negative balances; you cannot lose more than you put into a position.


=====

---
title: Can I always sell before a market ends?
summary: Usually, but it needs someone to take the other side.
contact: true
---

Selling before resolution needs someone to take the other side. In thin or
very lopsided markets there may be little demand for the side you hold, so you might not be able to
exit at the price you want, or at all.

You can always hold a position to resolution and redeem it on the outcome.


=====

---
title: Can I trade fractional shares?
summary: Yes. You buy by dollar amount, not by whole shares.
---

You enter the amount you want to spend, and you get however many shares that buys.

If a side costs 17¢ and you spend $1, you get about 5.8 shares. If you spend $5.37, you get about
31.5.
There is no need to work in whole shares.

This is why the panel asks for an amount in dollars rather than a number of shares.


=====

---
title: How do I place an order?
summary: Pick a side, enter an amount, and confirm.
---

Every market has two sides. On most markets they are **Yes** and **No**. Short-term crypto
markets, like Bitcoin over five minutes, use **Up** and **Down** instead, meaning up or down
against the **Price to beat** shown at the top of the market.

## Placing the order

1. Pick your side, then enter an amount.

   :::phone
   ![A market, with its two sides to choose from.](/assets/support/place-order.webp)
   :::

2. Check the **To win** figure, then choose **Confirm Trade**.

   :::phone
   ![The order panel, with an amount entered and what it pays if it wins.](/assets/support/confirm-trade.webp)
   :::

3. Your position appears in on the original screen under **Positions**
 

   :::phone
   ![The position under Positions, on the market screen.](/assets/support/positions-market.webp)
   :::

  and also in your [portfolio](/portfolio) under **Positions**,

   :::phone
   ![The same position in your portfolio.](/assets/support/positions-portfolio.webp)
   :::

You do not have to hold until the end. You can sell at any time, at whatever the market is paying
then. If you do hold to the end and the market resolves in your favor,
[you are paid automatically](/support/how-do-i-get-paid).


=====

---
title: Is there a minimum trade size?
summary: No, but a very small order costs more in fees than it is worth.
---

No. You can trade any amount.


=====

---
title: What is slippage, and how do I set it?
summary: The gap between the price you are quoted and the price you get.
---

Prices move while you are looking at them. Between the moment you are quoted a price and the moment
your order goes through, someone else may have traded and moved it. Slippage is that gap.

Your **slippage tolerance** is the most movement you are willing to accept. If the price moves
further than that before your order lands, the order does not go through at all. You are never
filled at a worse price than you accepted, and an order that does not go through costs you nothing.

## Where to find it

Open the menu at the top right and choose **Settings**. The first row is **Slippage Tolerance**.

![The Settings window, with Slippage Tolerance at the top.](/assets/support/slippage-settings.webp)

It starts on **Auto**, which picks a tolerance for you based on the market and the tokens involved.
You can also choose 0.3%, 0.5%, or type your own percentage.

## When to change it

A lower tolerance protects your price. Fewer orders go through, but none goes through at a price
you did not expect.

A higher tolerance suits a fast-moving market. The price on a short crypto market can move
repeatedly in the seconds it takes to confirm an order, and a tight tolerance will keep rejecting
it.

If an order keeps failing on a busy market, this is usually why.


=====

---
title: Do I need to KYC?
summary: No. But some countries cannot trade on World at all.
contact: true
---

World does not require KYC, but trading is not permitted from certain
[restricted jurisdictions](/support/which-countries-can-use-world).


=====

---
title: Which countries can use World?
summary: Most, but not all. The full list of restricted countries is here.
contact: true
---

World does not require KYC, but trading is not permitted from certain restricted jurisdictions.

World prediction markets are not available in the following countries and territories:

- Afghanistan
- Algeria
- Angola
- Australia
- Belarus
- Belgium
- Bolivia
- Brazil
- Bulgaria
- Burkina Faso
- Burundi
- Cameroon
- Canada
- Central African Republic
- China
- Côte d'Ivoire
- Cuba
- Democratic Republic of the Congo
- Ethiopia
- France
- Germany
- Haiti
- Hungary
- India
- Iran
- Iraq
- Ireland
- Italy
- Japan
- Kenya
- Laos
- Lebanon
- Libya
- Mali
- Malta
- Monaco
- Mozambique
- Myanmar
- Namibia
- Netherlands
- New Zealand
- Nicaragua
- Niger
- North Korea
- Poland
- Portugal
- Russia
- Singapore
- Slovakia
- Somalia
- South Sudan
- Sudan
- Switzerland
- Syria
- Taiwan
- Thailand
- Ukraine
- United Arab Emirates
- United Kingdom
- United States
- United States Minor Outlying Islands
- Venezuela
- Yemen
- Zimbabwe

Access is also blocked anywhere under comprehensive U.S. sanctions or where using the Services
would break local law, and this list can change over time.


=====

---
title: How do I withdraw my funds?
summary: Pick what you are withdrawing, say where it should go, and confirm.
contact: true
---

Choose **Withdraw** in your portfolio.

World can convert your funds as they leave, so you can be paid in the token and on the network
you want.

## Withdrawing funds

1. Pick the token you want to withdraw. If it is not listed, see
   [withdrawing a token that isn't listed](/support/withdraw-other-tokens).

   :::phone
   ![Choosing which token to withdraw.](/assets/support/withdraw-token.webp)
   :::

2. Enter an amount. There is a minimum, and **Min** fills it in for you. **Max** withdraws
   everything you hold.

   :::phone
   ![The Withdraw window, with the fees shown above the Withdraw button.](/assets/support/withdraw-details.webp)
   :::

3. Choose the **Currency** and the **Network** you want to be paid on.

4. Enter the **Recipient Address**. If you have an external wallet connected, **Use Connected**
   fills in its address for you.

5. Choose the arrow next to **You will receive** to see any fees and the maximum
   [slippage](/support/what-is-slippage).

6. Choose **Withdraw**.


=====

---
title: How do I withdraw a token that isn't listed?
summary: A manual fallback for older tokens that Withdraw in your portfolio does not support.
contact: true
---

**To withdraw CASH, USDC or SOL, use Withdraw in your portfolio.** That is the usual way to
withdraw, and it is covered in [How do I withdraw my funds?](/support/how-do-i-withdraw)

This page is only for tokens World does not support. It sends them to another Solana wallet
manually, and you pay the network fee in SOL. If you are withdrawing CASH, USDC, or SOL you should
use the Withdraw option in your portfolio.

:::note
Only do this if you are comfortable sending tokens on Solana yourself. A withdrawal sent to the
wrong address or to a wallet that does not support the token cannot be reversed. If you are unsure,
email support first.
:::

:::actions
withdraw
deposit
:::

## Withdrawing a token

1. Choose **Withdraw any token** above, and sign in if you are asked to.

2. Pick the token you want to withdraw.

3. Enter an amount, or choose **Max**.

4. Enter the **Solana** address it should go to.

5. Choose **Withdraw** and approve the transaction.

:::note
This sends tokens on Solana only, exactly as they are. Send them only to a Solana address that
accepts that token, or you may not be able to get them back.
:::

## Paying the network fee

Solana charges a small network fee for every transaction, paid in SOL. If you do not have enough,
**Withdraw** will tell you.

To add some, choose **Deposit to my wallet** above and send about 0.01 SOL to the address it shows
from another wallet or an exchange. Once it arrives, try your withdrawal again.
