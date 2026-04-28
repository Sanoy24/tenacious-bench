# Synthesis Memo 02: Datasheets and Data Cards

## Readings

- Timnit Gebru et al., *Datasheets for Datasets* (Communications of the ACM, 2021; originally `arXiv:1803.09010`)
- Mahima Pushkarna et al., *Data Cards: Purposeful and Transparent Dataset Documentation for Responsible AI* (FAccT 2022; `arXiv:2204.01075`)

## Thesis

These two papers together define the documentation bar for the benchmark. `Datasheets for Datasets` gives the lifecycle skeleton. `Data Cards` improves it by making documentation navigable, stakeholder-aware, and layered by abstraction. For Tenacious-Bench, the right move is to combine them: use the Gebru lifecycle sections as the mandatory backbone, then use the Pushkarna telescopic/periscopic/microscopic pattern to make the datasheet actually usable.

## What I am taking from the papers

`Datasheets for Datasets` is most useful in Sections 1.1, 2, and 3. Section 1.1 makes the dual audience explicit: creators need to reflect; consumers need enough information to decide responsibly. That is exactly the right frame for this challenge because the benchmark will be read by graders, teammates, and future strangers who may try to reproduce it. Section 2 matters because the paper does not treat documentation as a last-mile export task. It refines the questions through real use with product teams, feedback loops, and legal review. Section 3 gives the lifecycle grouping that the challenge explicitly wants us to follow: motivation, composition, collection process, preprocessing, uses, distribution, and maintenance.

`Data Cards` adds what Datasheets lacks in practice: structure for human usability at scale. Section 3.1 introduces principles like flexibility, modularity, extensibility, and accessibility. Section 3.2.1 is the key design move for this repo: questions should exist at multiple scopes. Telescopes provide an overview, periscopes capture operational detail, and microscopes capture the human rationale and policy decisions that cannot be inferred from the data alone. Section 3.4.1 then turns documentation quality into review dimensions: accountability, utility, quality, impact, and risk.

This layered model is ideal for our benchmark because we have two different jobs:

- satisfy the formal submission requirement
- make the dataset understandable enough that someone else can use it correctly

Without the layering, datasheets often become either too shallow to be useful or so dense that no one reads them.

## My disagreement with the papers

My disagreement is mainly with the anti-automation stance in `Datasheets for Datasets` Section 1.1 and the surrounding workflow argument. The paper explicitly says the process of creating a datasheet is not intended to be automated because automation works against the goal of reflection. I agree with that principle in spirit, but I think it is too absolute for this project.

For Tenacious-Bench, partial automation is not a threat to reflection; it is what makes reflection sustainable.

Why I disagree:

- some fields are factual inventory, not judgment
- we already have structured artifacts that can populate counts, partitions, and source-mode summaries automatically
- forcing humans to hand-copy reproducible facts increases error and wastes attention that should go to risk, rationale, and limitations

`Data Cards` itself gives a better compromise. Section 3.2.1 says periscopic content is often operational metadata and can often be automated more accurately than human input. I think that is the right implementation rule here:

- automate periscopic facts
- write telescopic summaries and microscopic rationales by hand

So my disagreement is not with the need for reflection. It is with the idea that reflection requires manual entry everywhere.

## Design consequence for Tenacious-Bench

For this repo, the documentation pattern should be:

- Telescopic:
  - what the benchmark is
  - what failure modes it targets
  - who should and should not use it
- Periscopic:
  - counts by partition
  - counts by source mode
  - counts by dimension
  - evaluator coverage
  - contamination protocol status
- Microscopic:
  - why these failure modes were chosen
  - why Path B is currently preferred
  - what the benchmark still misses
  - where public-signal lossiness enters the ground truth

That is much stronger than treating `datasheet.md` as a compliance artifact.

## What I will do because of these readings

1. Keep the Gebru lifecycle sections as the non-negotiable scaffold.
2. Use Pushkarna layering inside each section where helpful.
3. Auto-populate objective inventory fields when the repo can compute them.
4. Reserve human-authored detail for rationale, uncertainty, caveats, and use-risk tradeoffs.
5. Treat documentation quality as part of benchmark quality, not as packaging after the benchmark exists.

## Sources

- Gebru et al., *Datasheets for Datasets*, Sections 1.1, 2, and 3. `https://arxiv.org/abs/1803.09010`
- Pushkarna et al., *Data Cards*, Sections 3.1, 3.2.1, and 3.4.1. `https://facctconference.org/static/pdfs_2022/facct22-3533231.pdf`
