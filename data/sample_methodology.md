# Term Assurance Best Estimate Valuation Methodology (Illustrative)

**Status:** Illustrative document, fully fabricated for training and demonstration purposes. It does not describe any real insurer, portfolio, or basis, and must not be used for actual valuation work.

**Owner:** Head of Life Valuation (illustrative) | **Version:** 3.2 | **Effective:** Q2 reporting

## 1. Purpose and scope

This document sets out the methodology for deriving best estimate liabilities (BEL) for the level and decreasing term assurance portfolio. It covers data preparation, demographic and economic assumption setting, the projection approach, and the control framework. It applies to quarterly reporting and to ad hoc business projections that reuse the reporting basis. Unit-linked and annuity portfolios are out of scope and are covered by separate methodology documents.

## 2. Data sources and validation

Policy data is extracted from the administration system on the last working day of the quarter. The extract is reconciled to the prior quarter movement report: new business, deaths, lapses, maturities, and alterations must reconcile to within 0.05% of policy count and 0.10% of sum assured before the extract is accepted.

Field-level validation checks include: date of birth within plausible bounds, sum assured positive and below the underwriting ceiling, premium consistency with rate tables at issue, and benefit basis flags consistent with product codes. Records failing validation are quarantined and resolved with the administration team; unresolved records above the materiality threshold (0.25% of sum assured) require sign-off from the Head of Life Valuation before the valuation proceeds.

Claims experience data used for assumption setting is drawn from the claims ledger and matched to policy records by policy number and date. Unmatched claims above the investigation threshold are reviewed individually.

## 3. Mortality assumptions

Base mortality is set as a percentage of the standard industry table, split by sex, smoker status, and product line. The percentage is derived from an actual-versus-expected (A/E) analysis over the most recent five complete calendar years of portfolio experience.

Credibility weighting is applied where portfolio experience is thin. The credibility factor Z is derived from the number of expected claims in the experience cell; cells with fewer than 400 expected claims are blended with the pricing basis assumption using Z proportional to the square root of expected claims, capped at 1. Cells with fewer than 30 expected claims take the pricing basis assumption unadjusted.

Mortality improvements are applied from the mid-point of the experience period using the published industry improvement model, with a long-term improvement rate of 1.25% per annum for males and 1.00% for females, converging over 20 years. The long-term rate is reviewed annually by the Assumptions Committee.

Amounts-based A/E is the primary metric; lives-based A/E is monitored as a secondary check. Where the two diverge by more than 5 percentage points in a cell, the divergence is investigated for concentration effects before the assumption is finalised.

## 4. Lapse assumptions

Lapse rates are set by duration in force, split by premium frequency and distribution channel. The lapse curve reflects three phases: an early-duration peak in years one to two, a mid-duration plateau, and a modest rise approaching the end of the premium payment term for decreasing term business.

Lapse experience is analysed over the most recent three complete years using an exposure-based method. Duration cells with fewer than 500 policy-years of exposure are grouped with adjacent durations before rates are set.

A lapse loading of plus or minus 10% is tested as a standard sensitivity each quarter. No dynamic (economically driven) lapse adjustment is applied to the term portfolio; this position is reviewed annually against experience in stressed periods and was last reaffirmed by the Assumptions Committee following the most recent review.

## 5. Expense assumptions

Maintenance expenses are set on a per-policy basis from the annual expense analysis, allocated between acquisition, maintenance, and termination activity. The maintenance unit cost is expressed per policy in force and inflated at the expense inflation assumption, set as price inflation plus 0.75% to reflect wage-weighted cost pressure.

One-off project costs meeting the exceptional criteria in the expense analysis policy are excluded from the recurring unit cost but disclosed alongside the valuation results. Investment expenses are immaterial for this portfolio and are covered by the discount rate methodology rather than the expense assumption.

## 6. Discount rates

Cash flows are discounted on the prescribed risk-free curve published for the reporting date, without illiquidity or volatility adjustment for this portfolio. The curve is interpolated between published tenors using the published method and extrapolated beyond the last liquid point to the ultimate forward rate per the prescribed approach. The valuation system loads the curve directly from the published file; manual rate entry is not permitted.

## 7. Projection approach

Liabilities are projected policy by policy on a monthly time step over the remaining benefit term. Decrement order within each month is death, then lapse. Premiums are credited at the start of the month in which they fall due; claims are assumed paid at the end of the month of death, with a claims settlement delay of one month reflected in the discounting.

Negative reserves are permitted at policy level and are not floored, consistent with the best estimate objective; flooring applies only where a specific reporting basis requires it, in which case it is applied as a separate adjustment layer with its impact disclosed.

Model points are not used for the quarterly valuation; the full policy file is projected. Model point compression may be used for exploratory projections provided the compression error on BEL is demonstrated to be within 0.5% and the compression mapping is retained.

## 8. Controls and governance

The valuation operates under the following control framework:

- **Input controls.** Data reconciliation and validation as described in section 2, evidenced in the quarterly data pack.
- **Assumption governance.** All demographic and expense assumptions are approved by the Assumptions Committee at least annually, and whenever experience monitoring triggers an out-of-cycle review. The approval record includes the A/E evidence, the credibility treatment, and any expert judgement applied, with rationale.
- **Change control.** Model and methodology changes follow the model change policy: development, independent testing, parallel run against the prior version, and sign-off proportionate to the materiality band of the change. The parallel run difference must be explained to within the tolerance for the band.
- **Analysis of change.** Quarterly BEL movement is decomposed into new business, expected unwind, experience variances, assumption changes, methodology changes, and economic movements. Unexplained residual above 0.5% of opening BEL triggers investigation before results are released.
- **Sign-off.** Results are reviewed by the Head of Life Valuation and approved by the Chief Actuary. The sign-off pack includes the control evidence listed above and the sensitivity suite.

## 9. Limitations and sensitivities

The standard quarterly sensitivity suite comprises: mortality plus and minus 5%, lapse plus and minus 10%, maintenance expense plus 10%, expense inflation plus 1 percentage point, and interest rates plus and minus 100 basis points (parallel shift). Results are produced at portfolio level and for the largest product line separately.

Known limitations include: credibility blending relies on the pricing basis remaining a reasonable prior for thin cells; the absence of dynamic lapse assumes policyholder behaviour on this protection portfolio is not materially economically driven; and the monthly time step introduces a small discretisation effect quantified in the model validation report and accepted as immaterial.

## 10. Version history

- 3.2: Clarified negative reserve treatment and model point compression tolerance.
- 3.1: Updated long-term mortality improvement rates following annual review.
- 3.0: Rebuilt lapse analysis on exposure method; prior versions used a policy-year approximation.
