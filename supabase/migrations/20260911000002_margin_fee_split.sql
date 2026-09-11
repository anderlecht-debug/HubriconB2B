-- The fee split behind every price optimum.
--
-- margin_results carried one blended `amazon_fees` total, and pricing_engine
-- divided it by revenue to get a price-proportional fee rate. That treated a
-- fixed per-unit FBA fee as if it scaled with the price, which biases the
-- profit optimum P* downward and understates the gain from every increase.
--
-- margin.fee_split now separates the proportional rate (referral, and the
-- unnamed `other` residual) from the fixed per-unit charge (FBA fulfilment,
-- plus storage allocated across the period's units), and names its basis —
-- "itemized" where the channel's export separates them, "assumed_proportional"
-- where it reports one line. The column stores that blob so a later
-- measurement pass rebuilds the counterfactual with the same arithmetic that
-- made the promise.
alter table public.margin_results
  add column if not exists fee_split jsonb;

comment on column public.margin_results.fee_split is
  'Proportional fee rate f, fixed per-unit fee F, and the basis naming whether the channel''s export separated them. Consumed by models/pricing_engine.fee_terms.';
