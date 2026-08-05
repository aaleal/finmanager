# Module 7 — Multi-User & Household Scope (`modules/household`)

## Purpose
Enable multi-user access to a shared household's financial data while maintaining strict per-member privacy boundaries. Provide role-based access control (RBAC), automatic entity creation, member lifecycle management (invitation, onboarding, dependent profiles, separation), and persistent per-user entity perspective filters. Serve as the foundational permission and attribution layer for all other modules.

## Actors & User Stories
- *As a household owner*, I invite family members and grant roles to control who sees what.
- *As a member*, I see only my own finances and joint finances with my partner, not my sibling's individual transactions.
- *As a viewer (read-only guest)*, I can see summary reports but cannot edit or confirm anything.
- *As a dependent child*, my expenses are tracked under my profile, which a parent can view, but I have no login.
- *As a couple pre-separation*, we share a JOINT entity; post-separation we split assets and re-attribute history.

## Data Model
- **User**: `id, email, display_name, password_hash, role(OWNER|MEMBER|VIEWER|SYSTEM), is_deleted, is_dependent, locale, timezone, created_at, updated_at`.
- **Household**: `id, name, created_by, created_at, settings JSONB(default_entity_per_module, invitation_ttl_days, ...)`.
- **HouseholdMember**: `id, household_id, user_id, role(OWNER|MEMBER|VIEWER), is_dependent, joined_at, left_at (soft-delete), invited_by, invitation_accepted_at`.
- **Entity**: `id, household_id, type(INDIVIDUAL|JOINT|HOUSEHOLD), name, member_ids[], is_deleted, created_at, created_by`.
- **EntityMembership** (explicit M:N): `id, entity_id, household_member_id, added_at, added_by`.
- **InvitePending**: `id, household_id, email, role, token, expires_at, created_by, created_at`.
- **Session**: `id, user_id, household_id, created_at, expires_at, ip_address, user_agent, last_accessed_at, entity_id (persisted filter)`.
- **PermissionOverride**: `id, entity_id, member_id, module(receipts|banking|health|utilities|vehicles|assets), access_level(READ|WRITE|NONE), added_by, added_at`.
- **EntityReattribution** (immutable audit): `id, record_type, record_id, old_entity_id, new_entity_id, reason, approved_by, approved_at, created_at`.

## Functional Requirements
- **FR-7.1 Entity Attribution.** Every record carries `entity_id`. Types: INDIVIDUAL (1:1 member), JOINT (2 members), HOUSEHOLD (all). Queries always filter by entity visibility.
- **FR-7.2 Entity Selector & Persistence.** Global top-bar selector switches views; persisted per user/session in `Session.entity_id`; default falls back personal > joint > household.
- **FR-7.3 Role-Based Access Control.** OWNER (full control), MEMBER (read/write own + joint/household), VIEWER (read-only). Enforced on every endpoint via middleware.
- **FR-7.4 Invitation & Onboarding.** Time-limited magic links (`InvitePending.token`, default 7 days); pre-fill email/role; audit inviter.
- **FR-7.5 Dependent Profiles.** `is_dependent=true`, no password/session; parents create attributed expenses; appear in entity member lists.
- **FR-7.6 Member Lifecycle.** Soft-delete `left_at`; individual entity → read-only; joint entities require reconciliation; records stay in audit trail.
- **FR-7.7 Permission Granularity.** RBAC default; `PermissionOverride` for per-module fine-tuning.
- **FR-7.8 Entity Auto-Creation.** One INDIVIDUAL per member on setup/accept; JOINT auto-suggested on couple detection (opt-in); HOUSEHOLD on setup.
- **FR-7.9 GDPR Data Export & Deletion.** Per-member JSON export; deletion anonymizes PII, preserves audit links; financial history never hard-deleted.
- **FR-7.10 Session & CSRF Security.** Server-side sessions (Redis), UUID, tied to user+household+IP-range; httpOnly SameSite=Lax cookie; `X-CSRF-Token` (double-submit) on state-changing calls; token rotated on login; logout invalidates.

## Automation Rules
- Auto-create INDIVIDUAL per member (name = display_name).
- Two members flagged as couple → suggest JOINT (requires confirmation).
- HOUSEHOLD auto-created on setup; all members included.
- Every module query enforces `WHERE entity_id IN (user_visible_entity_ids)` from role + PermissionOverride + session entity.
- Member departure (`left_at`): revoke session tokens; individual entity → archived read-only.

## UI / Screens
- **Household Manager**: members, roles, join dates, invitation status; invite button.
- **Invitation Form**: email, role, message; send/resend; accept link (pre-login or logged-in).
- **Member Detail Card**: name, email, is_dependent, joined_at, role, per-module overrides, actions (change role, remove, impersonate [OWNER-only testing]).
- **Entity Selector** (global top bar): accessible entities dropdown; persist selection; reset.
- **Permission Settings**: modules × access-levels matrix; toggle `PermissionOverride`.
- **Data Subject Request**: GDPR export/delete UI; status tracking; confirmations.

## Security & RBAC
- **OWNER**: invite/remove, change roles, per-module overrides, household settings, approve re-attributions, impersonate (testing).
- **MEMBER**: own + joint + household per role; CRUD within accessible entities; confirm reviews for owned entities.
- **VIEWER**: read-only; no CRUD/confirmations/entity switching (locked to household view).
- **Per-Entity Visibility**: INDIVIDUAL → member + OWNER; JOINT → both member_ids + OWNER; HOUSEHOLD → all active members (role-gated).
- **Data Isolation**: queries join `Entity`, filter by role + `entity_id`; middleware checks `(user_role, requested_entity_id)`; no leaked records.
- **Cross-Household**: multi-household future; each session/query scoped to one active household.

## API Surface
- `POST /households` · `GET/PATCH /households/{id}`.
- `GET /households/{id}/members` · `POST /households/{id}/members/invite` · `GET /invitations/{token}` (public) · `POST /invitations/{token}/accept`.
- `PATCH /members/{id}` · `DELETE /members/{id}` (soft-delete).
- `POST /entities` (OWNER) · `GET /entities` · `PATCH /entities/{id}` · `POST/DELETE /entities/{id}/members`.
- `GET /sessions/current` · `POST /sessions/entity` (set filter, return new CSRF) · `POST /sessions/logout`.
- `PATCH /profile` · `POST /data-subject-request` · `GET /data-subject-requests/{id}/status`.

## Analytics & KPIs
- Active members per household + churn (left_at not null).
- Entity coverage (% records per entity type).
- Invitation acceptance rate & time-to-accept.
- Role distribution (% OWNER/MEMBER/VIEWER).
- Dependent spend per member.
- Entity re-attribution frequency (data-quality indicator).

## Edge Cases & Validation
- **Dependent without login**: name only; appears in entity lists/dropdowns; cannot self-register (OWNER may invite as full User later).
- **Member departure**: `left_at`; JOINT entities flagged `requires_review`; individual read-only; transactions visible to household but not edited.
- **Couple separation**: archive old JOINT; re-attribute via `EntityReattribution` (audit); system suggests 50/50 split.
- **Child ageing into login**: flip `is_dependent`, set password; gains INDIVIDUAL entity; prior records preserved.
- **Expense split across entities**: `payer_split` JSONB summing 100; `Link SPLIT_OF` edges track portions.
- **Entity selector default**: last session's entity; fall back personal → household → first accessible.
- **Concurrent sessions**: multiple devices → separate UUIDs; simultaneous access allowed.
- **Permission conflict**: `PermissionOverride` wins (most restrictive).

## Additional / Enriched Requirements
- **Couple Onboarding**: guided link → auto-create JOINT → prompt for shared assets.
- **Asset Split Scenario**: departure wizard to re-attribute JOINT assets (50/50 default); `EntityReattribution` with approval workflow.
- **Mobile-Only Viewer Role** (future): read-only guest expense entry (e.g., nanny uploads).
- **Audit Trail Enhancements**: role changes, invitations, departures, permission changes, re-attributions; query UI (who/what/when).
- **Invitation Best Practices**: auto-expire old invites; resend with backoff; bounce tracking; notify OWNER on non-accept.
- **Shared vs Private Tags**: tags scoped to `entity_id`; household view shows all, personal shows own.
- **Default Entity per Record Type** (settings): e.g., health→INDIVIDUAL, utilities→HOUSEHOLD, vehicles→JOINT.
- **Session Fixation Prevention**: new session UUID + cookie on accept+login; old invalidated.
- **Impersonation Logging**: AuditLog records start/end + reason; ≤1-hour windows; UI alert while impersonating.

## Open Questions / Decisions
| # | Question | Recommended Default |
|---|---|---|
| 1 | Member in multiple households? | Yes (future); one active household per session now. |
| 2 | Auto-confirm JOINT creation? | Require explicit confirmation. |
| 3 | Dependent creates account later? | Yes; flip `is_dependent`; old records preserved. |
| 4 | Session timeout? | 30 days (configurable); activity extends. |
| 5 | IP range for mobile revalidation? | /24; tighter for desktop. |
| 6 | Hard-delete departed member records? | No; retention forever; anonymize on GDPR request. |

## Definition of Done
- Household/member/entity CRUD tested (unit + integration).
- Invitation flow end-to-end (send, expire, accept, reject).
- Dependent profiles creatable + visible in selectors.
- RBAC middleware on ≥90% of endpoints (coverage).
- Entity selector persists across tabs; default logic tested.
- Session + CSRF validation (rotation, fixation prevention, IP bind).
- GDPR export valid JSON; deletion anonymizes PII, preserves audit.
- Entity auto-creation (setup, accept, couple linking) validated.
- `PermissionOverride` overrides role defaults; conflict scenarios tested.
- Audit trail complete.
- Seed: demo household with couple + 1 dependent + 1 viewer.
- Docs: invitation link format, session/CSRF flow diagram, GDPR runbook.

## Integration Contract
- **Exposes**: `Entity` (id, type, name, member_ids[]) and `HouseholdMember` (role, is_dependent) to all modules; RBAC context (user role, accessible entity IDs) as middleware; `entity_id` scoping contract; Session object (user_id, household_id, entity_id, csrf_token); `/sessions/current` returns user + household + accessible entities + current selection.
- **Consumes**: nothing (foundational).
- **Guarantees**: no financial data served unless the user's role grants access to the record's `entity_id`.
