# AGENTS.md

Follow the repository instructions in `CODE_GUIDELINES.md` when changing Python code.

## Public Interface Exception

- Keep the top-of-module forward declarations that summarize the intended public interface.
- These declarations are intentionally redundant at runtime. They let readers identify the public API before implementation details and must not be removed or moved as a declaration-order cleanup.
