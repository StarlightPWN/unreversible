# Passes
1. Preprocessing
    1. Rewrite all pushes into strings
    2. Combine anything that can be immediately combined into something simpler (so pushes followed by opcodes that consume, including `CALL_FUNC` for comparisons), this requires checking for `POP` for opcodes that don't consume
        - This requires the existence of higher-level opcodes, name them things like `CALL_FUNC_ADV2`
2. Decompilation
    1. Read labels and jumps, divide the node into basic blocks
    2. Create conditionals and choices