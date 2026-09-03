# Contributing

## Scope

This repository tracks the control plane design, protocol, and validation agent for zenoh-fleet-control. Keep changes focused on those boundaries.

## Working rules

- Prefer small, reviewable changes.
- Keep protocol changes mirrored in `protocol/`.
- Keep Python validation changes mirrored in `agent-python/README.md` when they affect usage.
- Do not add a new transport or file transfer mechanism without a documented reason.

## Validation

Before submitting a change:

- Run the agent syntax checks.
- Verify the local Zenoh flow if the change touches transport or session state.
- Update docs when behavior changes.

## Security notes

If your change affects access control, authentication, or transport encryption, update `SECURITY.md` and the sample config files in the same change.
