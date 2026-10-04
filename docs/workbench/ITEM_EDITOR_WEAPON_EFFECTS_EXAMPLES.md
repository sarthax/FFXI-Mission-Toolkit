# Weapon Effects examples

Examples for the Item Editor structured model:

- Fire damage, 20%, base 25: type 1, subeffect 1, damage 25, chance 20, element 1.
- Paralysis-style debuff: type 2 plus status/power/duration values verified for the target server lineage.
- HP drain: type 5 plus amount/chance and the appropriate drain presentation.
- Self-buff: generate a handoff blueprint; do not apply rows automatically until the target fork handler and proc numbering are verified.

Conditional versions use the same modifier bundle in `item_latents` plus the selected latent condition and parameter.
