# One product, priced for variability

Made-up data. Not a client. Not a result.

The lead time drives this buffer, and nobody has measured it. Measure the supplier before
changing the order.

## The table

| Product | Variance share: lead time | Variance share: demand | Buffer cost | Cheapest lever | Expected saving |
|---|---|---|---|---|---|
| The example product | 92.4% of the variance, on an assumed swing [inference] | 7.6% of the variance [inference] | $1,540 a year to hold 616 units of spare stock [inference] | Measure the supplier: two dates per order | Unknown until the lead time is measured |

## Formula and inputs

The reorder point is 2,416 units at a 95% service level, from μd = 40 units a day, σd = 15.4 units a day, μL = 45 days and σL = 9 days, all assumed [inference].

- The formula is ROP = μd·μL + z·√(μL·σd² + μd²·σL²), with z = 1.645 for a 95% service level and the μd, μL, σd, σL above [sourced: SUPPLY_VARIABILITY.md section 1.2].
- The lead time of 45 days is assumed, not measured [sourced: SUPPLY_VARIABILITY.md section 1.2].
- Demand over the wait is 40 units a day for 45 days, which is 1,800 units [inference].
- The demand part of the variance is 10,672 units squared and the lead-time part is 129,600 units squared [inference].
- Spare stock is 1.645 times the square root of their sum, which is 616 units [inference].
- Holding 616 units at a made-up $10 a unit and a made-up 25% a year costs $1,540 a year [inference].
- The cost of running out and the cost of rushing stock are not priced here, because the case has no margin and no freight rate to price them with.

## Plain reading

Almost all of the spare stock this product needs is there because the supplier's timing swings, not because sales do. The timing was typed in, not measured. So the cheapest thing to do is not to hold more or less stock. It is to write down two dates for every order, the day it was placed and the day it could be sold, and size the spare stock from those. Until then the buffer still has to be paid for in stock, in waiting or in rushed freight, and this table only says which of the three is being paid today.

## Next action

- Record the order date and the sellable date for the next six orders from this supplier.
