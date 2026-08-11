# Linear Algebra

## Vectors
A vector is an ordered list of numbers representing a point or direction in space. In ℝⁿ, a vector has n components.

Operations: addition (component-wise), scalar multiplication, dot product (a·b = Σaᵢbᵢ), cross product (3D only).

The magnitude of vector v = (v₁, v₂, ..., vₙ) is ||v|| = √(Σvᵢ²).

## Matrices
A matrix is a rectangular array of numbers with m rows and n columns (m×n matrix).

Matrix multiplication: if A is m×p and B is p×n, then AB is m×n where (AB)ᵢⱼ = Σₖ Aᵢₖ · Bₖⱼ. Note: AB ≠ BA in general.

Identity matrix I: square matrix with 1s on diagonal, 0s elsewhere. AI = IA = A.

## Systems of Linear Equations
Written as Ax = b where A is the coefficient matrix, x is the unknown vector, b is the constant vector.

Gaussian elimination: row operations to reduce to row echelon form, then back-substitute.

A system has a unique solution when det(A) ≠ 0 (A is invertible).

## Determinants
The determinant det(A) is a scalar value that indicates whether a matrix is invertible.
- 2×2: det([[a,b],[c,d]]) = ad − bc
- Property: det(AB) = det(A)·det(B)
- det(A) = 0 means A is singular (not invertible)

## Eigenvalues and Eigenvectors
An eigenvector v of matrix A satisfies Av = λv where λ is the corresponding eigenvalue.

To find eigenvalues: solve det(A − λI) = 0 (characteristic equation).

Eigendecomposition: A = PDP⁻¹ where D is diagonal matrix of eigenvalues, P has eigenvectors as columns.

## Vector Spaces
A vector space is a set of vectors closed under addition and scalar multiplication. Key concepts:
- Subspace: a subset that is itself a vector space
- Basis: a linearly independent spanning set
- Dimension: number of vectors in a basis
- Rank: dimension of the column space of a matrix
