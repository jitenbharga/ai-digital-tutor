# Probability and Statistics

## Basic Probability
Probability measures the likelihood of an event, ranging from 0 (impossible) to 1 (certain).

P(A) = (favorable outcomes) / (total outcomes) for equally likely outcomes.

Key rules:
- Complement: P(not A) = 1 − P(A)
- Addition: P(A or B) = P(A) + P(B) − P(A and B)
- Multiplication (independent): P(A and B) = P(A) · P(B)
- Conditional: P(A|B) = P(A and B) / P(B)

## Bayes' Theorem
P(A|B) = P(B|A) · P(A) / P(B)

Used to update beliefs given new evidence. The prior P(A) is updated to the posterior P(A|B) after observing B.

## Random Variables
A random variable assigns a numerical value to each outcome. Can be discrete (countable values) or continuous (any value in an interval).

Expected value: E[X] = Σ xᵢ · P(xᵢ) for discrete, ∫ x · f(x) dx for continuous.
Variance: Var(X) = E[(X − μ)²] = E[X²] − (E[X])².
Standard deviation: σ = √Var(X).

## Common Distributions
- Bernoulli: single trial, P(success) = p
- Binomial: n independent Bernoulli trials, P(k successes) = C(n,k) · pᵏ · (1−p)ⁿ⁻ᵏ
- Normal (Gaussian): bell curve, defined by mean μ and standard deviation σ. 68-95-99.7 rule.
- Poisson: counts of rare events in a fixed interval, P(k) = (λᵏe⁻λ) / k!

## Descriptive Statistics
- Mean (average): sum of values / count
- Median: middle value when sorted
- Mode: most frequent value
- Range: max − min
- IQR: Q3 − Q1 (interquartile range)

## Hypothesis Testing
1. State null hypothesis H₀ and alternative H₁
2. Choose significance level α (commonly 0.05)
3. Calculate test statistic from data
4. Find p-value: probability of seeing data this extreme if H₀ is true
5. If p-value < α, reject H₀

Common tests: z-test, t-test, chi-squared test, ANOVA.
