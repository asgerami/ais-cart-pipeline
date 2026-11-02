# Oct 30 playground runs, scored

Raw answers are in `raw/`, unchanged. Field names were mapped onto the kit's; every mapping is listed below.
Fields an answer doesn't have count as unknown. currency and other_conditions are not scored.

## Facts and invented details

| Checkout | Model | Run | Facts correct | Invented | Extra items | Flags caught | Statuses correct | Kit field names used |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Domainly | Muse Wonder 1.0 | 1 | 12 of 13 | 0 | 0 | 1 of 2 | not labeled | 4 of 12 |
| Domainly | Muse Spark 1.3 | 1 | 12 of 13 | 0 | 0 | 2 of 2 | 12 of 13 | 3 of 12 |
| Domainly | Muse Spark 1.3 | 2 | 12 of 13 | 0 | 0 | 2 of 2 | 12 of 13 | 4 of 12 |
| Sparkforge | Muse Wonder 1.0 | 1 | 10 of 10 | 0 | 1 | 1 of 2 | not labeled | 4 of 12 |
| Sparkforge | Muse Spark 1.3 | 1 | 10 of 10 | 0 | 1 | 2 of 2 | 9 of 10 | 6 of 12 |
| Cartwheel Office | Muse Wonder 1.0 | 1 | 14 of 14 | 0 | 0 | 0 of 0 | not labeled | 4 of 12 |
| Cartwheel Office | Muse Spark 1.3 | 1 | 14 of 14 | 0 | 0 | 0 of 0 | 14 of 14 | 4 of 12 |
| Cartwheel Office | Muse Spark 1.3 | 2 | 14 of 14 | 0 | 0 | 0 of 0 | 14 of 14 | 4 of 12 |

## Consistency (run 1 vs run 2)

| Checkout | Model | Same status and value | Same flags |
| --- | --- | --- | --- |
| Cartwheel Office | Muse Spark 1.3 | 16 of 16 fields | yes |
| Domainly | Muse Spark 1.3 | 16 of 16 fields | yes |

## Details per run

### Domainly, Muse Wonder 1.0, run 1 (`domainly_wonder_run1.json`)

- Wrong: `cancellation_terms` expected observed 'Auto-renew can be turned off in Settings', got unknown None
- Flags missed: multi_year_upfront
- Fields not in the kit: items, prices, total_due_today
- Mapping: original Wonder format: values copied; a value counts as observed, null as unknown; flags mapped by keyword; unmapped: renewal_date_not_specified, renewal_term_length_not_specified, cancellation_terms_not_stated

### Domainly, Muse Spark 1.3, run 1 (`domainly_spark_run1.json`)

- Wrong: `cancellation_terms` expected observed 'Auto-renew can be turned off in Settings', got unknown None
- Fields not in the kit: merchant_name, taxes, total_due_today, auto_renewal, renewal_price, renewal_term
- Mapping: merchant_name -> merchant; taxes -> tax; total_due_today -> total_due_now; auto_renewal: a true/false value; its evidence quote was used as the value; auto_renewal -> renewal_terms; line_items[0].price -> line_total; line_items[1].price -> line_total

### Domainly, Muse Spark 1.3, run 2 (`domainly_spark_run2.json`)

- Wrong: `cancellation_terms` expected observed 'Auto-renew can be turned off in Settings', got unknown None
- Fields not in the kit: taxes, total_due_today, initial_term, auto_renew, renewal_price, renewal_term
- Mapping: taxes -> tax; total_due_today -> total_due_now; auto_renew: a true/false value; its evidence quote was used as the value; auto_renew -> renewal_terms; line_items wrapped in status/value; inner rows use the wrapper's status; line_items[0].name: plain value with no status; counted as observed; line_items[0].term: plain value with no status; counted as observed; line_items[0].price: plain value with no status; counted as observed; line_items[0].price -> line_total; line_items[1].name: plain value with no status; counted as observed; line_items[1].price: plain value with no status; counted as observed; line_items[1].price -> line_total

### Sparkforge, Muse Wonder 1.0, run 1 (`sparkforge_wonder_run1.json`)

- Extra item: line_items[1]: extra line item 'Builder Pro trial' (on screen, likely counted twice)
- Flags missed: trial_converts_to_paid
- Fields not in the kit: items, prices, total_due_today
- Mapping: original Wonder format: values copied; a value counts as observed, null as unknown; flags mapped by keyword; unmapped: cancellation_location_unknown, exact_trial_end_date_and_time_not_specified, taxes_not_shown, card_required_to_start_trial

### Sparkforge, Muse Spark 1.3, run 1 (`sparkforge_spark_run1.json`)

- Wrong: `line_items[0].term` expected observed 'Monthly', got inferred 'monthly'
- Extra item: line_items[1]: extra line item 'Builder Pro trial' (on screen, likely counted twice)
- Fields not in the kit: plan_name, plan_price_display, plan_description, renewal_amount, renewal_interval, next_charge_date, trial_end_date, due_today, total_due_today, cta_text, card_requirement
- Mapping: total_due_today -> total_due_now; line_items wrapped in status/value; inner rows use the wrapper's status; plan_name, plan_price_display and renewal_interval read as the plan's line item; line_items[0].item_name -> name; line_items[0].item_amount -> line_total

### Cartwheel Office, Muse Wonder 1.0, run 1 (`cartwheel_wonder_run1.json`)

- Fields not in the kit: items, prices, total_due_today
- Mapping: original Wonder format: values copied; a value counts as observed, null as unknown; flags mapped by keyword; unmapped: renewal_terms_not_shown, cancellation_terms_not_shown

### Cartwheel Office, Muse Spark 1.3, run 1 (`cartwheel_spark_run1.json`)

- Fields not in the kit: cart_count, discount_code, discount_amount, shipping, tax_rate, tax_amount, total, renewal_price, renewal_date, billing_terms
- Mapping: discount_amount -> discounts; tax_amount -> tax; total -> total_due_now; discount_code kept as a separate field (the amount is what's scored)

### Cartwheel Office, Muse Spark 1.3, run 2 (`cartwheel_spark_run2.json`)

- Fields not in the kit: merchant_name, cart_item_count, discount, shipping, total
- Mapping: merchant_name -> merchant; discount -> discounts; total -> total_due_now

