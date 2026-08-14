# Calculus

## Limits
The limit of f(x) as x approaches a, written lim(x→a) f(x) = L, means f(x) gets arbitrarily close to L as x gets close to a.

Key limit laws: limits of sums, products, and quotients equal the sums, products, and quotients of limits (when defined).

Important limit: lim(x→0) sin(x)/x = 1.

## Derivatives
The derivative f'(x) measures the instantaneous rate of change of f at x. Defined as:
f'(x) = lim(h→0) [f(x+h) − f(x)] / h

Key rules:
- Power rule: d/dx[xⁿ] = nxⁿ⁻¹
- Product rule: d/dx[fg] = f'g + fg'
- Quotient rule: d/dx[f/g] = (f'g − fg') / g²
- Chain rule: d/dx[f(g(x))] = f'(g(x)) · g'(x)

## Applications of Derivatives
- Finding maxima/minima: set f'(x) = 0, check second derivative
- Related rates: differentiate both sides of an equation with respect to time
- Linear approximation: f(x) ≈ f(a) + f'(a)(x − a) near x = a

## Integrals
The integral ∫f(x)dx is the antiderivative of f. The definite integral ∫[a,b] f(x)dx gives the signed area under f between a and b.

Fundamental Theorem of Calculus: If F'(x) = f(x), then ∫[a,b] f(x)dx = F(b) − F(a).

Key rules:
- Power rule: ∫xⁿ dx = xⁿ⁺¹/(n+1) + C (n ≠ −1)
- ∫1/x dx = ln|x| + C
- ∫eˣ dx = eˣ + C

## Integration Techniques
- Substitution (u-sub): change variables to simplify
- Integration by parts: ∫u dv = uv − ∫v du
- Partial fractions: decompose rational functions before integrating
