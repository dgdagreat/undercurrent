"""Machine-learning risk model — a data-driven complement to the rule-based score.

This package adds a supervised default-risk model alongside the transparent,
rule-based Undercurrent score. It exists to demonstrate the full ML lifecycle on
this domain: a reproducible labeled-data pipeline (dataset.py), a shared feature
layer (features.py), training + evaluation (train.py), and explainable serving
(model.py). The rule-based score stays the product's backbone; the ML model is
the "what would a learned model say, and can it be trusted?" second opinion.

Honesty note: labels are synthetic. Real default outcomes don't exist for these
fictional businesses, so dataset.py draws each label *stochastically* from a
business's latent fundamentals plus noise (see its docstring). That keeps the
learning problem realistic — features are noisy estimates of a latent risk, so
the model can't hit a perfect score — and it's the methodology, not a real
default predictor, that this showcases.
"""
