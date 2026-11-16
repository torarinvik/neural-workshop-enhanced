# The Cipher Abyss: the plan to perfect it

Files: model `neural_workshop/cipherabyss.py` (rule language, families per
stage, Machine/build/deal, Run, Mind = reference active learner,
autopilot); screen `neural_workshop/ui/cipherabyss.py` (HandTask); env
`nwenv/cipherabyss.py` (23 ports); tests `tests/test_cipherabyss.py`;
Readme section "#### The Cipher Abyss" under Reasoning.

House rules: one port per step for agents; every dealt round passed by the
reference player (H.deal); idle and random fail; band check clean; smoke
suite green; Readme rung table kept true; commit only when asked, with the
Co-Authored-By line. Suites are slow: run them in the background, early.

After each phase: run test_cipherabyss, the menu/env suites, the smoke
suite and check_band; screenshot rungs 1, 7, 13, 20, 25, 40 and look at
them; fix what looks wrong; give a short report.

## Phase 1: measure before changing
1. `tools/bench_cipher.py`: for every rung 1-60, deal 200 machines; record
   family size, reference pass rate, experiments the reference used,
   seconds per deal, how often build() returns None, and the share of tests
   decided by majority vote rather than unanimity.
2. Baseline players: idle, random, repeat the input, always the identity,
   the most common rule of the stage, and a one-hypothesis greedy player
   (commits to the first consistent rule). Pass rate per rung. Any shortcut
   player above 5% on a rung is a defect to fix in Phase 3.
3. Put the numbers in a "Measured" paragraph of the Readme section.

## Phase 2: a richer, properly layered language
4. Move the rule language into a typed AST module
   `neural_workshop/cipherlang.py`: Prim, Seq, If, Alt, Except; an
   interpreter, a pretty-printer, a parser for the printed form, and
   canonicalisation (rot n then rot m = rot n+m, shift a then shift b,
   rev rev = id, ...). Dedupe every family by behaviour on a probe set so
   the hypothesis count is honest.
5. New primitives, each introduced at a named rung and documented: hidden
   position permutations; interleave/deinterleave; mirror halves; count the
   run; affine a*x+b over Z_k; per-position maps (odd/even positions);
   XOR-like ops over Z_2^m when k is a power of two; GF(4)/GF(8)
   multiplication at the cryptography stage; an invertible Feistel-style
   round built from known parts.
6. A real hidden-language stage between state and nested: the input is a
   tiny program (some symbols opcodes, some data) and the output is its
   result. 2-4 opcodes whose meanings are drawn from the primitives.
7. A real rules-that-modify-rules stage: a meta-state changes which
   primitive a branch applies after certain inputs (seeing symbol s swaps
   branches; every third run composes one more step).
8. Length-changing machines at a later stage (dedupe, duplicate, drop every
   other) with the answer row sized to match.
9. Keep the stage order and ladder table in grade() and the Readme in
   sync; every stage starts gently and grows inside itself.

## Phase 3: discoverability guarantees
10. build(): after the reference's experiments, ALL still-consistent rules
    must agree on every test input (unanimity, not majority). Deal only then.
11. Choose test inputs that separate the true rule from rules that were
    consistent before the last few experiments, so lucky guessing fails.
12. Minimum description: the true rule must be among the shortest
    consistent rules (canonical size) after the reference's experiments.
13. Fix any shortcut player found in Phase 1.
14. Average deal time under 0.5 s at every rung: profile Mind; cache
    predictions per (rule, history); numpy or bit-packing if needed.

## Phase 4: the laboratory, for humans
15. Hypothesis board: assemble a rule from the language's blocks (rotate
    2, if first is red, ...) and press Check to run it against the whole
    notebook, rows green or red. Agents reach it through extra ports or a
    documented small text protocol (decide and document).
16. "Predict before you run" toggle; the notebook marks hits and misses.
17. Notebook: scroll through everything, sort, mark rows, per-position
    differences, colour-blind safe symbols (shape and number always),
    numbers toggle.
18. Animation: input taken in, gears turn, output comes out symbol by
    symbol with its note.
19. End screen: the rule in words and as a block diagram, the most
    informative experiments, and what a perfect experimenter would have run.
20. A first-time tutorial round at rung 1 with arrows (remembered in the
    config).
21. Full keyboard play and full mouse play, both tested; resizing keeps
    the layout; no overlapping text at 640x400 or 2560x1440.

## Phase 5: executable answers and higher-level tests
22. From composition up: win by submitting the rule from the hypothesis
    board, judged by behavioural equivalence on a large hidden probe set.
23. From nested up: one generalisation question on a longer row than any
    seen in the experiments.
24. A "two machines" round: same or not, and if not, the input that tells
    them apart.
25. An "invert it" round at the reversible stage: given outputs, give the
    inputs.

## Phase 6: a universe that remembers
26. Per-player library of discovered operators in the user data dir.
27. Disguised reuse: later rungs bring back earlier operators under new
    symbol assignments or new structure; the end screen says "you met this
    one at rung N".
28. A held-out operator family never seen below rung 30, to test transfer;
    documented.
29. Optional plain-text notebook export, for external memory.

## Phase 7: scoring genuine reasoning
30. Per round: hidden-test accuracy, experiments used vs the reference's,
    bits gained per experiment (hypothesis count before and after),
    description length of a submitted rule, time to solve. Shown on the end
    screen and in session results; given to the agent env as info, not as
    reward.
31. The adaptive ladder stays pass/fail; richer metrics go into the
    results file with a documented schema.
32. Benchmark mode (fixed seed list per stage, held-out operators on) and a
    script that scores an agent's run.

## Phase 8: an open-ended top
33. Above rung 40: random programs from the whole language, depth growing
    with the rung, still filtered by unanimity and minimum description.
34. Fewer experiments and longer rows grow slowly; a hard ceiling on
    per-deal compute.

## Phase 9: polish, sound and docs
35. Sound: each symbol's note, a thinking hum, and (end screen only) a tone
    for experiments that split the hypotheses well vs ones that told nothing.
36. Readme: full stage table, a language reference with one example per
    primitive, how discoverability is guaranteed, the measured numbers, the
    agent protocol.
37. Tests: every primitive and stage, parser/printer round trip,
    canonicalisation, unanimity, shortcut players, persistence, hypothesis
    board, keyboard and mouse play, resizing, env boundary, audio.

## Done when
Every phase is implemented, measured and documented; the bench shows the
reference passing 100% of dealt rounds, every shortcut player at or under
5% on every rung, average deal time under 0.5 s; all suites green; band
check clean; screenshots at the listed rungs look right. Then stop and ask
before committing.
