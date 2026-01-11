# Intent Authority Implementation Plan

## Overview
Redesign the Focus Dashboard Assistant to be intent-safe, deterministic, and powerful through a 4-layer architecture.

## Phase 1: Core Architecture (intent_authority.py)
- [x] Create IntentDetectionLayer (Layer 1) - deterministic regex/heuristics
- [x] Create AIIntentSuggestionLayer (Layer 2) - advisory AI with confidence
- [x] Create IntentAuthorityLayer (Layer 3) - rules engine, clarification logic
- [x] Create ActionExecutionLayer (Layer 4) - pure business logic
- [x] Implement confidence scoring system
- [x] Implement clarification strategy with pending intents

## Phase 2: Refactor ai_parser.py
- [x] Update SmartParser to work with new layers
- [ ] Modify parse() to return structured intent candidates
- [ ] Ensure AI suggestions are advisory, not authoritative
- [ ] Add structured JSON output for AI

## Phase 3: Update UI (ui.py)
- [ ] Update ChatView to handle clarification responses
- [ ] Add pending intent storage and retrieval
- [ ] Display clarification options to user
- [ ] Handle user responses to clarifications

## Phase 4: Hard Rules Implementation
- [ ] Queries never create/modify data
- [ ] Classes REQUIRE days + start + end
- [ ] Tasks REQUIRE meaningful title
- [ ] Ambiguity leads to clarification, not mutation
- [ ] Low confidence triggers clarification

## Phase 5: ACE Integration
- [ ] Record decisions to skillbook
- [ ] Record user corrections
- [ ] Learn patterns (phrasing → intent)
- [ ] ACE remains memory/analytics, NOT authority

## Success Criteria
- [ ] Questions never add tasks
- [ ] Assistant asks clarification instead of guessing
- [ ] AI errors don't cause data corruption
- [ ] System feels predictable and safe

## Files to Create/Modify
- `intent_authority.py` (NEW - core architecture)
- `ai_parser.py` (REFACTOR - support new layers)
- `ui.py` (UPDATE - handle clarification)

